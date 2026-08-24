/*
 * Icon-Vorschau für Tabler-Icon-Felder im Django-Admin.
 *
 * Ein Feld, in das man "tools-kitchen-2" tippt, ist ohne Rückmeldung blindes
 * Raten — ein Tippfehler fällt sonst erst auf der Live-Seite auf. Deshalb: das
 * eingetippte Icon direkt neben dem Feld rendern, dazu ein Link in die Galerie,
 * in der man den Namen nachschlägt. Rendert nichts, wenn der Name unbekannt ist
 * (die Webfont zeigt dann einfach kein Glyph) — genau das ist die Rückmeldung.
 *
 * Greift auf jedes Input, dessen Name auf "icon" endet — also auch auf die
 * dynamisch per "add another" nachgeladenen Inline-Formulare.
 */
(function () {
    "use strict";

    var GALLERY_URL = "https://tabler.io/icons";

    function decorate(input) {
        if (input.dataset.iconPreviewReady) return;
        input.dataset.iconPreviewReady = "1";

        var wrap = document.createElement("span");
        wrap.style.cssText = "display:inline-flex;align-items:center;gap:.5rem;margin-left:.5rem;";

        var preview = document.createElement("i");
        preview.style.cssText = "font-size:1.6rem;line-height:1;width:1.6rem;text-align:center;";

        var link = document.createElement("a");
        link.href = GALLERY_URL;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = "Browse icon names ↗";
        link.style.cssText = "font-size:.8125rem;";

        function render() {
            var name = (input.value || "").trim();
            preview.className = name ? "ti ti-" + name : "";
            preview.title = name ? "ti-" + name : "";
        }

        input.addEventListener("input", render);
        render();

        wrap.appendChild(preview);
        wrap.appendChild(link);
        input.parentNode.insertBefore(wrap, input.nextSibling);
    }

    function scan(root) {
        (root || document).querySelectorAll('input[name$="icon"]').forEach(decorate);
    }

    document.addEventListener("DOMContentLoaded", function () {
        scan(document);
        // Django feuert das beim Hinzufügen einer Inline-Zeile (jQuery-Event).
        if (window.django && window.django.jQuery) {
            window.django.jQuery(document).on("formset:added", function (event) {
                scan(event.target);
            });
        }
    });
})();
