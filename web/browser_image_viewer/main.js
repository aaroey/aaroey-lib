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

function handleFile(e) {
  let URL = window.webkitURL || window.URL;
  let max_width = 400;
  let max_height = 300;
  let ctx = document.getElementById('canvas').getContext('2d');
  let url = URL.createObjectURL(e.target.files[0]);
  let img = new Image();
  img.onload = function() {
    let ratio = 1;
    if (img.width > max_width) {
      ratio = max_width / img.width;
    }
    if (ratio * img.height > max_height) {
      ratio = max_height / img.height;
    }
    ctx.scale(ratio, ratio);
    ctx.drawImage(img, 0, 0);
  };
  img.src = url;
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
  if (header4B == "89504e47") {
    return MimeType.PNG;
  } else if (header4B == "47494638") {
    return MimeType.GIF;
  } else if ([ "ffd8ffe0", "ffd8ffe1", "ffd8ffee", "ffd8ffdb" ].includes(
                 header4B)) {
    return MimeType.JPEG;
  } else if (header4B == "52494646") {
    return MimeType.WEBP;
  } else if (header4B.substring(0, 4) == "424d") {
    return MimeType.BMP;
  }
  return MimeType.UNKNOWN;
}

// Please refer to:
// https://stackoverflow.com/questions/18299806/how-to-check-file-mime-type-with-javascript-before-upload
function selectImageFile(blob) {
  return new Promise((resolve, reject) => {
    // Fast path: check file extension.
    if (blob.type.includes("image")) {
      // Use any type other than UNKNOWN is fine.
      resolve(blob);
      return;
    }

    // Slow path: read the magic numbers.
    let reader = new FileReader();
    reader.onloadend = function(e) {
      let arr = new Uint8Array(e.target.result);
      let header = "";
      for (let i = 0; i < arr.length; i++) {
        header += arr[i].toString(16);
      }
      if (imgMimeType(header) == MimeType.UNKNOWN) {
        resolve(null);
      } else {
        resolve(blob);
      }
    };
    // Only read the first 4 bytes.
    reader.readAsArrayBuffer(blob.slice(0, 4));
  });
}

function handleDir(e) {
  let promises = [];
  for (const f of e.target.files) {
    promises.push(selectImageFile(f));
  }
  Promise
      .all(promises) // Wait for the resolutions.
      .then(results => {
        const cols = 3;
        const width = Math.floor(getWidth() / cols) - 10;

        let table = document.getElementById('img_table');
        table.innerHTML = '';
        let i = 0;
        let tr = null;
        for (const f of results) {
          if (f == null) {
            continue;
          }
          if (i % 3 == 0) {
            tr = document.createElement('tr');
            table.appendChild(tr);
          }
          ++i;

          let img = document.createElement('img');
          // f.webkitRelativePath is based on html dir, so won't work.
          img.src = URL.createObjectURL(f);
          img.width = width;

          let td = document.createElement('td');
          td.appendChild(img);
          tr.appendChild(td);
        }
      });
}

function addEventListener(id, eventName, handler) {
  let elem = document.getElementById(id);
  elem.addEventListener(eventName, handler, false);
}

window.onload = function() {
  // addEventListener('input_single', 'change', handleFile)
  addEventListener('input_dir', 'change', handleDir)
};
