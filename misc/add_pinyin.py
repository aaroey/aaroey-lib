# Need to: pip install pypinyin==0.40.0
import sys
from pypinyin import constants
from pypinyin import core

def mylen(words):
  if constants.RE_HANS.match(words):
    return len(words) * 2
  return len(words)

def align(h, p):
  """Align the two lists."""
  hlen, plen = mylen(h), mylen(p)
  if False:
    print('\033[93m=> "%s" : %d\033[0m' % (str(p), plen))
    print('\033[93m=> "%s" : %d\033[0m' % (str(h), hlen))
  while hlen + 2 <= plen:
    h = ' ' + h + ' '
    hlen += 2
  while plen + 2 <= hlen:
    p = ' ' + p + ' '
    plen += 2
  # Left-aligned.
  if hlen < plen:
    h += ' '
    hlen += 1
  elif plen < hlen:
    p += ' '
    plen += 1
  if False:
    print('\033[93m=> "%s" : %d\033[0m' % (str(p), plen))
    print('\033[93m=> "%s" : %d\033[0m' % (str(h), hlen))
  return h, p

def mypinyin(hans, style=core.Style.TONE, heteronym=False, errors='default',
             strict=True, v_to_u=False, neutral_tone_with_five=False):
  pinyin = core.Pinyin(core._mixConverter(
      v_to_u=v_to_u, neutral_tone_with_five=neutral_tone_with_five))

  # Run the conversion.
  segmented_hans = pinyin.seg(hans)
  hans = []
  pyins = []
  for words in segmented_hans:
    py = pinyin._converter.convert(
        words, style, heteronym, errors, strict=strict)
    # print('\033[92m=> %s -> %s\033[0m' % (words, str(py)))
    if len(py) > 1:
      # `py` is a list of list of pinyins, each pinyin for one Chinese
      # character. For non Chinese characters len(py) must be 1 (no translation
      # happening), so len(py)>1 means there are multiple Chinese characters,
      # and so in this case `words` must be Chinese characters, 
      assert len(words) == len(py), '"%s" (%d) vs "%s" (%d)' % (
          words, len(words), py, len(py))
      for c in words:
        hans.append(c)
    else:
      hans.append(words)
    for p in py:
      assert len(p) == 1
      pyins.append(p[0])

  # Align the two lists.
  assert len(hans) == len(pyins)
  aligned_hans = []
  aligned_pyins = []
  for i in range(len(hans)):
    h, p = align(hans[i], pyins[i])
    aligned_hans.append(h)
    aligned_pyins.append(p)

  # Concat the words into fixed-width sentences and yield them.
  line_width = 60
  cur_pyins = ''
  cur_hans = ''
  for i in range(len(aligned_hans)):
    h, p = aligned_hans[i], aligned_pyins[i]
    cur_pyins += p
    cur_hans += h
    if len(cur_pyins) > line_width:
      if cur_pyins[-1] != '\n':
        if False:  # Used with markdown
          cur_pyins += '  '
          cur_hans += '  '
        cur_pyins += '\n'
        cur_hans += '\n'
      yield cur_hans, cur_pyins
      cur_hans = ''
      cur_pyins = ''
    else:  # Decide whether to add a space to separate the next pinyin.
      is_end = (i == len(aligned_hans) - 1)
      cur_is_han = constants.RE_HANS.match(hans[i])
      next_is_han = (not is_end and constants.RE_HANS.match(hans[i+1]))
      cur_py_ends_with_space = p.endswith(' ')
      next_py_starts_with_space = (
          not is_end and aligned_pyins[i+1].startswith(' '))
      if (cur_is_han and next_is_han and not cur_py_ends_with_space and
          not next_py_starts_with_space):
        cur_pyins += ' '
        cur_hans += ' '
  if cur_pyins:
    yield cur_hans, cur_pyins

def AddPinyin(in_path, out_path):
  with open(out_path, 'w') as out_f:
    with open(in_path, 'r') as in_f:
      cnt = 0
      for l in in_f.readlines():
        for hans, pyins in mypinyin(l):
          if False:
            cnt += 1
            if cnt > 10: return
            print('\033[92m=> %s\033[0m' % str(pyins))
            print('\033[93m=> %s\033[0m' % str(hans))
          else:
            out_f.write(pyins)
            out_f.write(hans)

if __name__ == '__main__':
  AddPinyin(*sys.argv[1:])
