import os
import shutil

import utils


def move_files(src_root_dir: str, dst_root_dir: str, debug: bool):
  """Move files from src_root_dir to dst_root_dir with the same dir structure."""
  i = 0
  for cur_dir, _, files in os.walk(src_root_dir):
    for file in files:
      src_path = os.path.join(cur_dir, file)
      for suffix in ('.ds_store',):
        if src_path.lower().endswith(suffix):
          print(f'\033[93m=> Skipping {src_path}\033[0m')
          continue

      relative_path = os.path.relpath(src_path, src_root_dir)
      dst_path = os.path.join(dst_root_dir, relative_path)
      if debug:
        print(f'\033[93m=> {src_path}\033[0m')
        print(f'{dst_path}')
        i += 1
        if i > 30:
          return
      else:
        utils.safe_move(src_path, dst_path)


if __name__ == '__main__':
  src_root_dir = '/Users/laigd/.Trash/2'
  dst_root_dir = '/Users/laigd/Documents/images/eee/网页'
  debug = False
  move_files(src_root_dir=src_root_dir, dst_root_dir=dst_root_dir, debug=debug)
