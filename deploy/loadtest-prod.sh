#!/usr/bin/env bash
#
# Load test against production — including resource sampling on the server.
#
# Why the wrapper: shared hosting caps memory per account (Uberspace: 1536 MB),
# and that budget is usually shared with whatever else runs on the account. A
# plain throughput test says nothing about how close the app gets to that limit
# under load — but that is the number that matters on the conference day. So
# RAM and load average are sampled once per second while the test runs.
#
# Usage:
#   deploy/loadtest-prod.sh                 # 100 users, 60 s
#   deploy/loadtest-prod.sh 150 90          # 150 users, 90 s
#
# Configure the target via environment variables:
#   LMA_URL           base URL of the deployment          (required)
#   LMA_REMOTE_HOST   user@host for the resource sampling (required)
#   LMA_SSH_KEY       ssh key to use                      (default: ~/.ssh/id_ed25519)
#   LMA_SERVICE       systemd user unit name              (default: lma-connect.service)
#   LMA_RAM_LIMIT_MB  account RAM limit for the verdict   (default: 1536)
#
# Run it *before* the conference, not during.

set -uo pipefail

USERS="${1:-100}"
DURATION="${2:-60}"
URL="${LMA_URL:-}"
REMOTE_HOST="${LMA_REMOTE_HOST:-}"
SSH_KEY="${LMA_SSH_KEY:-$HOME/.ssh/id_ed25519}"
SERVICE="${LMA_SERVICE:-lma-connect.service}"
RAM_LIMIT="${LMA_RAM_LIMIT_MB:-1536}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -z "$URL" || -z "$REMOTE_HOST" ]]; then
    echo "ERROR: set LMA_URL=https://... and LMA_REMOTE_HOST=user@host" >&2
    exit 2
fi

SAMPLES="$(mktemp -t lma-loadtest-samples)"
trap 'rm -f "$SAMPLES"' EXIT

echo "Load test: $USERS users, ${DURATION}s, against $URL"
echo "Resource sampling on $REMOTE_HOST is running alongside."
echo

# Background sampling: RSS of the app service, total RSS of the account, load.
ssh -i "$SSH_KEY" -o ConnectTimeout=20 -o BatchMode=yes "$REMOTE_HOST" \
    "for i in \$(seq 1 $((DURATION + 30))); do
        svc=\$(systemctl --user show $SERVICE -p MemoryCurrent --value 2>/dev/null)
        all=\$(ps -u \$USER -o rss= | awk '{s+=\$1} END {print int(s/1024)}')
        load=\$(cut -d' ' -f1 /proc/loadavg)
        echo \"\$((svc/1024/1024)) \$all \$load\"
        sleep 1
    done" > "$SAMPLES" 2>/dev/null &
SAMPLER_PID=$!

"$HERE/loadtest.py" --url "$URL" --users "$USERS" --duration "$DURATION" --ramp 15
TEST_EXIT=$?

kill "$SAMPLER_PID" 2>/dev/null
wait "$SAMPLER_PID" 2>/dev/null

echo "── Server resources during the run ──────────────────"
if [[ ! -s "$SAMPLES" ]]; then
    echo "  (no samples — is the SSH connection working?)"
else
    awk -v limit="$RAM_LIMIT" '
        { app[NR]=$1; all[NR]=$2; load[NR]=$3
          if ($1>appmax) appmax=$1
          if ($2>allmax) allmax=$2
          if ($3>loadmax) loadmax=$3
          appsum+=$1; allsum+=$2; loadsum+=$3 }
        END {
            printf "  App RAM        avg %4d MB   max %4d MB\n", appsum/NR, appmax
            printf "  Account total  avg %4d MB   max %4d MB   (limit %d MB)\n", allsum/NR, allmax, limit
            printf "  Load           avg %5.2f     max %5.2f\n", loadsum/NR, loadmax
            printf "\n"
            if (allmax > limit * 0.85) print "  WARNING: close to the RAM limit — reduce workers, raise threads."
            else if (allmax > limit * 0.65) print "  Note: RAM headroom is shrinking, keep an eye on it."
            else printf "  RAM headroom: %d MB (%d %% of the limit used)\n", limit-allmax, allmax*100/limit
        }
    ' "$SAMPLES"
fi

echo
echo "── Errors in the server journal during the run ──────"
ssh -i "$SSH_KEY" -o ConnectTimeout=20 -o BatchMode=yes "$REMOTE_HOST" \
    "journalctl --user -u $SERVICE --since '-$((DURATION + 60)) seconds' --no-pager \
     | grep -icE 'traceback|database is locked|worker timeout|critical'" \
    | xargs -I{} echo "  critical lines: {}"

exit $TEST_EXIT
