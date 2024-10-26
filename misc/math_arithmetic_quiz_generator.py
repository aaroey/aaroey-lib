import itertools
import collections
import random


def safe_eval(problem):
  return eval(problem, {}, {})


def generate_problems():
  # yapf: disable
  numbers = [
      # (a, -a), (b, -b), (c, -c), (d, -d)
      (73, -73), (27, -27), (27, -27), (73, -73)
  ]
  parentheses = [
      '{0} {1} {2} {3} {4} {5} {6}',
      '{0} {1} ({2} {3} {4}) {5} {6}',
      '({0} {1} {2}) {3} ({4} {5} {6})',
      '{0} {1} ({2} {3} {4} {5} {6})',
      '{0} {1} ({2} {3} ({4} {5} {6}))',
  ]
  # yapf: enable
  operators = ['+', '-']

  problems = []
  for nums in itertools.product(*numbers):
    for ops in itertools.product(operators, repeat=3):
      if '-' not in ops:
        # It should contain at least one substraction.
        continue
      for parens in parentheses:
        problem = parens.format(
            nums[0], ops[0], nums[1], ops[1], nums[2], ops[2], nums[3]
        )
        problems.append(problem)
  return problems


def filter_and_select(all_problems):
  values = collections.defaultdict(list)
  for problem in all_problems:
    values[safe_eval(problem)].append(problem)

  for k, v in values.items():
    print(f'Possible result: {k}, num problems with that value: {len(v)}')

  selected_problems = []
  for k, v in values.items():
    if k in (0, 200, -200):
      for problem in v:
        selected_problems.append(problem)

  random.shuffle(selected_problems)
  return selected_problems


def run():
  all_problems = generate_problems()
  print(f'\033[93m=> num of total problems: {len(all_problems)}\033[0m')
  selected_problems = filter_and_select(all_problems)
  for problem in selected_problems:
    print(f'{problem}  ={safe_eval(problem)}')

  print(f'num of selected problems: {len(selected_problems)}')


run()
