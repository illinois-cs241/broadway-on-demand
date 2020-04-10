/**
 * Activate drag and drop file upload. The HTML need a drag and drop box, and a hidden
 * file type input (for click and upload). If file_extensions parameter is given, will only allow dropping
 * file with the extensions in the file_extensions string to be uploaded. If file_extensions is not
 * provided, will accept any file type.
 * Note: file_extensions supports file with no extension as well.
 *
 * @param box_selector The selector for the drag and drop box.
 * @param input_selector The selector for the input with type="file", usually hidden
 * @param file_extensions A string of comma separated file extensions. e.g. ".txt,.cvs"
 * @return function() A function that when called, return the current uploaded file. If no file has
 *  been uploaded, the function returns undefined.
 */
function fileDragDrop(box_selector, input_selector, file_extensions = undefined) {
    var current_file = undefined;

    function uploadSuccess(box_selector, file) {
        $(box_selector).text(`Current file: ${file.name}`).addClass("on-full");
    }

    function checkFileExtension(file_name, file_types) {
        let allowed_types = file_types.split(',');
        // search for the last "." in file name
        let i = file_name.lastIndexOf(".");
        let extension = "";
        if (i >= 0) {
            extension = file_name.slice(i);
        }
        return allowed_types.includes(extension);
    }

    $(box_selector).on("drag dragstart dragend dragover dragenter dragleave drop", function(e) {
        e.preventDefault();
        e.stopPropagation();
    });

    $(box_selector).on("dragover", function (e) {
        $(this).removeClass("on-full").addClass("on-drag");
    }).on("dragleave drop", function (e) {
        $(this).removeClass("on-drag");
    });

    $(box_selector).on("drop", function (e) {
        if (e.originalEvent.dataTransfer &&
            e.originalEvent.dataTransfer.files &&
            e.originalEvent.dataTransfer.files.length) {
            let file = e.originalEvent.dataTransfer.files[0];
            if (file_extensions === undefined || checkFileExtension(file.name, file_extensions)) {
                current_file = file;
                uploadSuccess(box_selector, current_file);
            }
        } else {
            $(box_selector).text("Please drop files");
        }
    });

    $(box_selector).on("click", function () {
        $(input_selector).click();
    });

    $(input_selector).on("change", function () {
        let file = $(input_selector)[0].files[0];

        if (file) {
            current_file = file;
            uploadSuccess(box_selector, current_file);
        }
    });

    return () => { return current_file }
}