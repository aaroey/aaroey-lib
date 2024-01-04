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
function selectImageFile(file) {
  // Note: since 'onloadend' is async and there seems to be no way to wait for
  // it to complete (i.e. making it sync), we need to return a Promise here.
  // Also, given the usage of 'file' below (e.g. checking the file.type, etc),
  // 'file' need to be an actual File object, not a Promise.
  return new Promise((resolve, reject) => {
    // Note: this executor function (i.e. this Promise constructor argument,
    // which is a function) will run immediately by the Promise constructor.
    // The 'resolve' function provides users a way to fullfill the value
    // of this Promise. It has nothing to do with the downstream callbacks
    // chained using '.then()'.
    // In this case, the 'resolve' function will be called asynchronously in
    // FileReader.onclick, i.e. it may not have been run when this executor
    // function exits.

    // Fast path: check file extension.
    if (file.type.includes('image')) {
      // Use any type other than UNKNOWN is fine.
      resolve(file);
      return;
    }

    // Slow path: read the magic numbers.
    let reader = new FileReader();
    reader.onloadend = function(e) {
      let arr = new Uint8Array(e.target.result);
      let header = '';
      for (let i = 0; i < arr.length; i++) {
        header += arr[i].toString(16);
      }
      if (imgMimeType(header) == MimeType.UNKNOWN) {
        resolve(null);
      } else {
        resolve(file);
      }
    };
    // Only read the first 4 bytes.
    reader.readAsArrayBuffer(file.slice(0, 4));
  });
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

destDirHandle = null;  // The destination dir to move the selected images to.

// Add or remove an image from the selected image list.
async function moveSelectedImage(img, file) {
  if (destDirHandle == null) {
    let msg = 'Destination directory is not set!';
    alert(msg);
    throw new Error(msg);
  }
  let targetDir = null;
  let movedCntElem = getMovedCnt();
  let movedCnt = parseInt(movedCntElem.innerHTML);

  if (file.imgViewerCurDirHandle == file.imgViewerSrcDirHandle) {
    targetDir = destDirHandle;
    img.classList.add('selected');  // Add css style to mask the image.
    movedCntElem.innerHTML = movedCnt + 1;
  } else if (file.imgViewerCurDirHandle == destDirHandle) {
    targetDir = file.imgViewerSrcDirHandle;
    img.classList.remove('selected');
    movedCntElem.innerHTML = movedCnt - 1;
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

// Reset the webpage status.
function reset() {
  getMovedCnt().innerHTML = 0;
}

// Tracks the handle of the last opened src dir. We added this since setting
// {'id': <some-string>} when calling showDirectoryPicker() doesn't seem to
// work, see below.
lastSrcDir = null;

async function handleSrcDir() {
  reset();

  let options = {
    id: 'src_dir',  // Doesn't seem to work.
  };
  if (lastSrcDir !== null) {
    options['startIn'] = lastSrcDir;
  }
  const dirHandle = await window.showDirectoryPicker(options);
  lastSrcDir = dirHandle;
  getSrcDirName().innerHTML = 'Chosen src directory: ' + dirHandle.name;
  displayImages(await processDir(dirHandle, ''));
}

async function handleDstDir() {
  reset();

  let options = {
    id: 'dst_dir',
    mode: 'readwrite',
  };
  if (destDirHandle == null) {
    options['startIn'] = 'desktop';
  } else {
    options['startIn'] = destDirHandle;
  }
  const dirHandle = await window.showDirectoryPicker(options);
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
