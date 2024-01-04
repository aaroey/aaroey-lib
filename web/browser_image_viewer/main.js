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

destDirHandle = null;  // The destination dir to move the selected images to.

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
function selectImageFile(file) {
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
function getMovedCnt() {
  return elemById('num_moved');
}
function getImgTable() {
  return elemById('img_table');
}
function getSrcDirName() {
  return elemById('src_dir_name');
}
function getDstDirName() {
  return elemById('dst_dir_name');
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

// Add or remove an image from the selected image list.
async function moveSelectedImage(img, file) {
  if (destDirHandle == null) {
    let msg = 'Destination directory is not set!';
    alert(msg);
    throw new Error(msg);
  }
  let targetDir = null;
  let movedCntElem = getMovedCnt();
  let selectedCnt = parseInt(movedCntElem.innerHTML);

  if (file.imgViewerCurDirHandle == file.imgViewerSrcDirHandle) {
    targetDir = destDirHandle;
    img.classList.add('selected');  // Add css style to mask the image.
    movedCntElem.innerHTML = selectedCnt + 1;
  } else if (file.imgViewerCurDirHandle == destDirHandle) {
    targetDir = file.imgViewerSrcDirHandle;
    img.classList.remove('selected');
    movedCntElem.innerHTML = selectedCnt - 1;
  } else {
    throw new Error('Invalid file dir handle!');
  }
  await file.imgViewerFileHandle.move(targetDir);
  file.imgViewerCurDirHandle = targetDir;
}

function fileCmp(lhs, rhs) {
  return lhs.imgViewerRelativePath.localeCompare(rhs.imgViewerRelativePath);
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
          img.onclick = async () => moveSelectedImage(img, f);

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
          (file) => {
            // Adds custom properties to store extra information.
            file.imgViewerRelativePath = path + '/' + handle.name;
            file.imgViewerSrcDirHandle = dirHandle;
            file.imgViewerCurDirHandle = dirHandle;
            file.imgViewerFileHandle = handle;
            return selectImageFile(file)
          }
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

async function handleSrcDir() {
  const dirHandle = await window.showDirectoryPicker({
    // Set 'id' to an arbitrary identifier to remember the last directory.
    // TODO: doesn't seem to work.
    id: 'src_dir',
  });
  getSrcDirName().innerHTML = 'Chosen src directory: ' + dirHandle.name;
  displayImages(await processDir(dirHandle, ''));
}

async function handleDstDir() {
  const dirHandle = await window.showDirectoryPicker({
    id: 'dst_dir',
    mode: 'readwrite',
  });
  destDirHandle = dirHandle;
  getDstDirName().innerHTML = 'Chosen dst directory: ' + dirHandle.name;
}

function addEventListener(id, eventName, handler) {
  let elem = elemById(id);
  elem.addEventListener(eventName, handler, false);
}

window.onload = function() {
  addEventListener('src_dir', 'click', handleSrcDir)
  addEventListener('dst_dir', 'click', handleDstDir)
};
