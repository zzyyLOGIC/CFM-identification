"""Read a uniform fixed quota and supported population queries from affirmative protocol clauses."""
import re
from functools import lru_cache

NUM = r"(?:[0-9]+|[一二两三四五六七八九十]+)"
UNIT = r"(?:个单位|个节点|个对象|人|家|个|站|台|区|线|席|组|处|条|座|仓)"
UNCERTAIN = r"不(?:是|再|能|可|准|足)|不能|无法|没有|不详|未(?:知|定|给|提供)|尚未|拟(?:采用|按)|假设|假如|若|可能|只对|仅对|部分|分层|分组|按组|每组|各组|有放回"


def named_units(clause, nodes):
    """Parse a complete roster list without splitting names that themselves contain 和 or 与."""
    @lru_cache(maxsize=None)
    def at(pos):
        matches = []
        for name in nodes:
            if not clause.startswith(name, pos):
                continue
            tail = pos + len(name)
            if tail == len(clause):
                matches.append((name,))
            else:
                separator = re.match(r"\s*[、，,与和及]\s*", clause[tail:])
                if separator:
                    matches.extend((name, *suffix) for suffix in at(tail + separator.end()))
            if len(matches) > 1:
                return matches[:2]
        return matches
    if len(clause) > 2048 or len(nodes) > 256:
        return None
    options = at(0)
    return list(options[0]) if len(options) == 1 else None


def integer(s):
    if s.isdigit():
        return int(s)
    digits = {c:i for i,c in enumerate('零一二三四五六七八九')}
    s = s.replace('两','二')
    if s in digits:
        return digits[s]
    if s.count('十') == 1:
        a,b = s.split('十')
        if (not a or a in digits) and (not b or b in digits):
            return digits.get(a,1)*10 + digits.get(b,0)
    return None


def uniform_quota(statements, nodes):
    values = set()
    for line in statements:
        if '无放回' not in line or not re.search(r'等概率|等机会|均匀',line):
            continue
        if re.search(UNCERTAIN,line):
            return None
        for match in re.finditer(r'(?:抽取|抽出|选出|选定|抽)\s*('+NUM+r')\s*'+UNIT,line):
            values.add(integer(match[1]))
        total=re.search(r'(?:从|在)('+NUM+r')'+UNIT+r'.{0,12}无放回',line)
        if total and integer(total[1]) != len(nodes):
            return None
    if len(values)==1:
        m=values.pop()
        if m is not None and 0<m<=len(nodes):
            return m
    return None


def population_queries(rows, group):
    """An exact joint law for (own, peer event, outcome) also supplies both conditional means."""
    positive=[]
    for row in rows:
        line=row['quote']
        if re.search(r'(?:不(?:可|能)|无法|不允许|不提供|禁止).{0,10}(?:查询|获得|提供).{0,22}(?:结果|结局|联合律|条件均值)|'
                     r'(?:仅对|只对|限于)部分.{0,15}(?:逐|查询|联合律)|(?:仅限|只限).{0,8}(?:去年|上期|部分)|只有边际可查',line):
            return []
        if not re.search(r'总体(?:联合(?:分布|律)|条件均值|条件平均)',line):
            continue
        if re.search(r'不能|不可|无法|不含|不包括|不提供|仅有边际|只有边际|假如|若能|拟(?:采集|提供)|未(?:知|提供)|仅(?:能|可)?.{0,4}(?:一端|左端|右端)',line):
            return []
        if not re.search(r'(?:可|允许|能够|提供).{0,12}查[询取]|(?:已提供|可提供)',line):
            continue
        each=re.search(r'(?:逐|每|各)(?:一)?(?:个单位|个节点|个对象|站|仓|店|单位|对象|节点|人)',line)
        named=all(n in line for n in group)
        if not (each or named):
            continue
        joint=('联合' in line and re.search(r'本人|本站|本单位|自身|自己',line)
               and re.search(r'邻.{0,8}暴露|同伴.{0,6}状态',line) and re.search(r'结果|结局',line)
               and re.search(r'原(?:设计|抽签|分配)',line))
        both=(re.search(r'条件(?:均值|平均)',line) and re.search(r'上述事件|两端|两个事件|两种比较情形',line))
        if joint or both:
            positive.append(row)
    return positive
