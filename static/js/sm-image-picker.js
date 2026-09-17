(function () {
    "use strict";

    if (window.SmImagePicker) return;
    window.SmImagePicker = true;
    var selections = new WeakMap();

    document.addEventListener("change", function (event) {
        var input = event.target;
        if (!input.matches('input[type="file"]')) return;
        var picker = input.closest("[data-image-picker]");
        if (!picker || !input.files.length) return;
        var label = picker.querySelector("label.sm-profile-avatar-edit");
        var status = picker.querySelector("[data-image-status]");
        var state = selections.get(picker);
        if (!state) {
            state = {original: label.firstElementChild.cloneNode(true), version: 0};
            selections.set(picker, state);
        }
        var version = ++state.version;
        var file = input.files[0];
        input.setCustomValidity("");
        if (file.size > 5 * 1024 * 1024 || (file.type && !["image/jpeg", "image/png", "image/webp"].includes(file.type))) {
            label.firstElementChild.replaceWith(state.original.cloneNode(true));
            status.textContent = "Selecione uma imagem JPEG, PNG ou WebP de até 5 MiB.";
            input.setCustomValidity(status.textContent);
            return;
        }
        var reader = new FileReader();

        function current() {
            return picker.isConnected && state.version === version;
        }

        function fail() {
            if (!current()) return;
            label.firstElementChild.replaceWith(state.original.cloneNode(true));
            status.textContent = "Não foi possível gerar a prévia. Selecione outra imagem.";
        }

        status.textContent = "Carregando prévia…";
        reader.onerror = fail;
        reader.onabort = fail;
        reader.onload = function () {
            if (!current()) return;
            var preview = new Image();
            preview.className = "sm-profile-avatar";
            preview.alt = "Prévia da imagem selecionada";
            preview.onload = function () {
                if (!current()) return;
                label.firstElementChild.replaceWith(preview);
                status.textContent = "Prévia — clique em Salvar para confirmar";
            };
            preview.onerror = fail;
            preview.src = reader.result;
        };
        reader.readAsDataURL(file);
    });
})();
