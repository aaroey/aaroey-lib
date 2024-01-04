function getWidth() {
  return Math.max(
      document.body.scrollWidth, document.documentElement.scrollWidth,
      document.body.offsetWidth, document.documentElement.offsetWidth,
      document.documentElement.clientWidth);
}

function getHeight() {
  return Math.max(
      document.body.scrollHeight, document.documentElement.scrollHeight,
      document.body.offsetHeight, document.documentElement.offsetHeight,
      document.documentElement.clientHeight);
}

const MimeType = {
  UNKNOWN : 0,
  JPEG : 1,
  PNG : 2,
  WEBP : 3,
  GIF : 4,
  BMP : 5,
};

Object.freeze(MimeType);

// See more mime types in: http://en.wikipedia.org/wiki/List_of_file_signatures
function imgMimeType(header4B) {
  if (header4B == '89504e47') {
    return MimeType.PNG;
  } else if (header4B == '47494638') {
    return MimeType.GIF;
  } else if ([ 'ffd8ffe0', 'ffd8ffe1', 'ffd8ffee', 'ffd8ffdb' ].includes(
                 header4B)) {
    return MimeType.JPEG;
  } else if (header4B == '52494646') {
    return MimeType.WEBP;
  } else if (header4B.substring(0, 4) == '424d') {
    return MimeType.BMP;
  }
  return MimeType.UNKNOWN;
}

// Please refer to:
// https://stackoverflow.com/questions/18299806/how-to-check-file-mime-type-with-javascript-before-upload
function selectImageFile(file, fullRelativePath) {
  // Adds a custom property (.fullRelativePath) to store the relative path info.
  file.fullRelativePath = fullRelativePath;

  // Fast path: check file extension.
  if (file.type.includes('image')) {
    // Use any type other than UNKNOWN is fine.
    return file;
  }

  // Slow path: read the magic numbers.
  let reader = new FileReader();
  let result = null;
  reader.onloadend = function(e) {
    let arr = new Uint8Array(e.target.result);
    let header = '';
    for (let i = 0; i < arr.length; i++) {
      header += arr[i].toString(16);
    }
    if (imgMimeType(header) == MimeType.UNKNOWN) {
      result = null;
    } else {
      result = file;
    }
  };
  // Only read the first 4 bytes.
  reader.readAsArrayBuffer(file.slice(0, 4));
  return result;
}

function elemById(id) {
  return document.getElementById(id);
}
function getSelectedTable() {
  return elemById('selected_imgs_table');
}
function getSelectedCnt() {
  return elemById('num_selected');
}
function getImgTable() {
  return elemById('img_table');
}
function getInputDirName() {
  return elemById('input_dir_name');
}
function getSelectedImagesDiv() {
  return elemById('selected_imgs_div');
}
function getToggleSelectedBtn() {
  return elemById('toggle_selected');
}
function getNumColumns() {
  return elemById('num_columns');
}

function newRowWithContent(data) {
  td = document.createElement('td');
  td.innerHTML = data;
  tr = document.createElement('tr');
  tr.appendChild(td);
  return tr;
}

// Show or hide the selected image names.
function toggleSelectedNamesState() {
  let div = getSelectedImagesDiv();
  let btn = getToggleSelectedBtn();
  let display = div.style.display;
  if (display == 'none' || display == '') {
    div.style.display = 'block';
    btn.innerHTML = 'Hide selected file names';
  } else {
    div.style.display = 'none';
    btn.innerHTML = 'Show selected file names';
  }
}

function copySelectedNamesToClipboard() {
  // NOTE: using regex need to unescape the html content which is hard.
  // var text = getSelectedTable().innerHTML;
  // .replace(/<[^>]+(>|$)/g, "");
  // text = text.replace(/<tr><td>/g, "'");
  // text = text.replace(/<\/td><\/tr>/g, "'\n");
  let table = getSelectedTable();
  let text = '';
  for (r of table.rows) {
    for (c of r.cells) {
      if (text.length) text += '\n';
      text += c.textContent;
    }
  }
  navigator.clipboard.writeText(text).then(
      function() {
        console.log('Successfully copied selected names to clipboard!');
        console.log(
            'Run `rsync -R <files> <dst>` to copy them over to dst folder.');
      },
      function(err) { console.error('Failed to copy selected names: ', err); });
}

function clearSelections() {
  getSelectedCnt().innerHTML = '0';
  getSelectedTable().innerHTML = '';
  let table = getImgTable();
  for (r of table.rows) {
    for (c of r.cells) {
      c.firstChild.classList.remove('selected');
    }
  }
}

// Add or remove an image from the selected image list.
function toggleImgSelectionState(img, file) {
  const path = file.fullRelativePath;
  let selectedCntElem = getSelectedCnt();
  let selectedCnt = parseInt(selectedCntElem.innerHTML);
  let table = getSelectedTable();
  let hasRow = false;
  for (r of table.rows) {
    if (r.firstChild.textContent == path) {
      hasRow = true;
      table.removeChild(r);
      img.classList.remove('selected');  // Add css style to mask the image.
      selectedCntElem.innerHTML = selectedCnt - 1;
      break;
    }
  }
  if (!hasRow) {
    img.classList.add('selected');
    table.appendChild(newRowWithContent(path));
    selectedCntElem.innerHTML = selectedCnt + 1;
  }
}

function fileCmp(lhs, rhs) {
  return lhs.fullRelativePath.localeCompare(rhs.fullRelativePath);
}

// Shows images processed by selectImageFile(), represented as 'imgPromises',
// to the web page.
function displayImages(imgPromises) {
  Promise
      .all(imgPromises) // Wait for the resolutions.
      .then(results => {
        const cols = parseInt(getNumColumns().value);
        const width = Math.floor(getWidth() / cols) - 20;

        let table = getImgTable();
        table.innerHTML = '';
        let i = 0;
        let tr = null;
        let images = results.filter(function(f) { return f != null; });
        images = images.sort(fileCmp);
        for (const f of images) {
          if (f == null) {
            // selectImageFile() will emit null for non-image files.
            continue;
          }
          if (i % cols == 0) {
            tr = document.createElement('tr');
            table.appendChild(tr);
          }
          ++i;

          let img = document.createElement('img');
          // f.webkitRelativePath is '' when using Chrome web apis, so won't
          // work.
          img.src = URL.createObjectURL(f);
          img.width = width;
          img.onclick = () => { toggleImgSelectionState(img, f); };

          let td = document.createElement('td');
          td.appendChild(img);
          tr.appendChild(td);
        }
      });
}

// Recursively add images from sub directories.
async function processDir(dirHandle, pathPrefix) {
  let promises = [];
  let path = pathPrefix + '/' + dirHandle.name;
  for await (const handle of dirHandle.values()) {
    if (handle.kind == 'file') {
      promises.push(
        handle.getFile().then(
          (file) => selectImageFile(file, path + '/' + handle.name)
        )
      );
    } else if (handle.kind == 'directory') {
      let subPromises = await processDir(handle, path);
      promises = promises.concat(subPromises);
    }
    // Skip other file kinds.
  }
  return promises;
}

async function handleDir() {
  const dirHandle = await window.showDirectoryPicker({
    // Set 'id' to an arbitrary identifier to remember the last directory.
    // TODO: doesn't seem to work.
    id: 'images',
  });
  getInputDirName().innerHTML = 'Chosen directory: ' + dirHandle.name;
  displayImages(await processDir(dirHandle, ''));
}

function addEventListener(id, eventName, handler) {
  let elem = elemById(id);
  elem.addEventListener(eventName, handler, false);
}

window.onload = function() {
  addEventListener('input_dir', 'click', handleDir)
  addEventListener('toggle_selected', 'click', toggleSelectedNamesState)
  addEventListener('copy_selected', 'click', copySelectedNamesToClipboard)
  addEventListener('clear_selected', 'click', clearSelections)
};
