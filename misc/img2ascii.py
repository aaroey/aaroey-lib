# Reference: https://github.com/kiteco/python-youtube-code/blob/master/ascii/ascii_convert.py
import os
import sys
from PIL import Image

ASCII_CHARS = ["@", "#", "S", "%", "?", "*", "+", ";", ":", ",", "."]

# Resize image according to a new width
def resize_image(image, new_width):
  width, height = image.size
  ratio = height/width
  new_height = int(new_width * ratio / 2)
  resized_image = image.resize((new_width, new_height))
  return resized_image

# Convert each pixel to grayscale.
def grayify(image):
  grayscale_image = image.convert("L")
  return grayscale_image
  
# Convert pixels to a string of ascii characters
def pixels_to_ascii(image):
  pixels = image.getdata()
  characters = "".join([ASCII_CHARS[pixel//25] for pixel in pixels])
  return characters 

def run(path, new_width=200):
  if not isinstance(new_width, int):
    assert new_width.isnumeric()
    new_width = int(new_width)
  path = os.path.expanduser(path)
  try:
    image = Image.open(path)
  except Exception as e:
    print(path, " is not a valid pathname to an image:", str(e))
    return
  
  new_image_data = pixels_to_ascii(grayify(resize_image(image, new_width)))
  pixel_count = len(new_image_data)  
  ascii_image = "\n".join([
      new_image_data[index:(index+new_width)]
      for index in range(0, pixel_count, new_width)
  ])
  
  # Print result
  print(ascii_image)
  # Save result to "/tmp/ascii_image.txt"
  with open("/tmp/ascii_image.txt", "w") as f:
    f.write(ascii_image)
 
if __name__ == '__main__':
  run(*sys.argv[1:])
