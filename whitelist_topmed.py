import re

whitelist = '''
pjvh@umich.edu
'''

whitelist = [re.sub('#.*', '', l).strip().lower() for l in whitelist.split('\n')]
whitelist = [l for l in whitelist if l]
assert all(' ' not in l and '@' in l for l in whitelist)
