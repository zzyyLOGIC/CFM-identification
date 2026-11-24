"""Read a uniform fixed quota and supported population queries from affirmative protocol clauses."""
import re
from contextvars import ContextVar
from functools import lru_cache

NUM = r"(?:[0-9]+|[一二两三四五六七八九十]+)"
UNIT = r"(?:个单位|个节点|个对象|人|家|个|站|台|区|线|席|组|处|条|座|仓)"
UNCERTAIN = r"不(?:是|再|能|可|准|足)|不能|无法|没有|不详|未(?:知|定|给|提供)|尚未|拟(?:采用|按)|假设|假如|若|可能|只对|仅对|部分|分层|分组|按组|每组|各组|有放回"

# Nested verification stages share the source-reading rules of the report
# being replayed. ContextVar keeps simultaneous HTTP requests independent.
reading_revision = ContextVar('network_protocol_reading_revision',default=None)


def treated_neighbor_majority(clause, treatment, *, require_otherwise_zero=False):
    """Match the full exposure definition to the solver's strict majority of treated neighbors."""
    if not treatment:
        return False
    text = re.sub(r'\s+', '', clause).replace('，', ',')
    predicate = re.sub(r'\s+', '', treatment)
    actions = [re.escape(predicate), r'处理(?:取值|值)?(?:为|=)1']
    # A protocol may call the declared switch simply “启用” or “开启”.
    switch = re.match(r'启用|开启|开放|开通', predicate)
    if switch:
        actions.append(switch[0])
    active = '(?:' + '|'.join(actions) + ')'
    peer = r'(?:合作邻居|直接邻居|邻居|邻区|邻站|合作对象|相邻(?:的)?(?:站点|网点|门店|节点|单位))'
    majority = r'(?:严格)?(?:超过(?:一半|半数|50%)|过半|多于一半)'
    event = (rf'(?:{peer}中{majority}(?:的{peer})?{active}|{majority}(?:的)?{peer}{active}'
             rf'|{peer}中{active}的比例{majority})')
    prefix = r'(?:(?:本题|本研究)(?:的|中)?)?(?:(?:同伴暴露|暴露|同伴状态)(?:定义为|为|指)[：:]?)?'
    one = r'(?:时|则)?,?(?:(?:同伴)?(?:暴露|状态))?(?:记为?|编码为|为)1'
    zero = r',否则(?:记为?|为)0'
    ending = zero if require_otherwise_zero else rf'(?:{zero})?'
    return re.fullmatch(prefix + event + one + ending + r'(?:,平票(?:记为?|为)0)?', text) is not None


def independent_draw(text):
    """Independence must describe the draws, not the absence of outcome interference."""
    revision=reading_revision.get()
    single=r'独立(?:抽签|分配|随机|投币)|(?:彼此|各自|相互)独立'
    equivalent=r'(?:每|各).{0,12}(?:分别|各自)抽签[，,](?:各次抽签)?互不影响'
    negative=r'不能|无法|未必|不一定|尚未|是否|未知|不清楚|不独立|并非|不保证|不再|不采用|共用|相关抽签'
    if revision is not None and revision<23:
        return bool(re.search(single,text))
    if revision==23:
        return not re.search(negative,text) and bool(re.search(single,text) or re.search(equivalent,text))
    clauses=[s.strip() for s in re.split(r'[。；;！？\n，,]',text) if s.strip()]
    draw=r'抽签|分配|投币|随机|抽取|中签|签之间|独立性|相关抽签|共用.{0,8}(?:签|硬币)'
    reject=negative+r'|抽签相关|不相互独立|互相影响|非独立|存疑|未确认|未决定|未证实|不成立|假如|如果|拟采用|拟按'
    uncertain_design=r'可能.{0,12}(?:抽签|分配|投币|共用|相关|独立|取决于)|(?:抽签|分配|投币|签次)(?:规则|独立性)?(?:有)?可能'
    for i,clause in enumerate(clauses):
        # A limitation on inferring a design from observed counts does not
        # negate a separately stated assignment protocol. It cannot establish one either.
        if re.fullmatch(r'(?:实际(?:使用|启用|参加|处理)(?:人数|数量)|(?:单日|一次)(?:观测|样本|记录))'
                        r'(?:本身)?(?:不能|无法|不足以)(?:证明|推出|确定)(?:随机分配方式或概率|分配规则|抽签的独立性)',clause):
            continue
        refers_to_draw=re.search(draw,clause) or '独立' in clause and not re.search('潜在结果|观测结果',clause)
        if refers_to_draw and (re.search(reject,clause) or re.search(uncertain_design,clause)):
            return False
        if i and re.search(draw,clauses[i-1]) and re.fullmatch(r'(?:此项|这项假设|这一点)?(?:尚未确认|尚未决定|不成立|并非如此)',clause):
            return False
    for i,clause in enumerate(clauses):
        if re.search(draw,clause) and not re.search(r'潜在结果|观测结果',clause):
            if re.search(single,clause) or re.search(r'(?:抽签|签次|投币)(?:之间)?(?:相互|互相|彼此)独立',clause):
                return True
            if i+1<len(clauses) and re.fullmatch(r'(?:各次抽签)?互不影响',clauses[i+1]) and re.search(r'(?:分别|各自)抽签',clause):
                return True
    return False


def common_probability(text, nodes):
    """A uniform Bernoulli probability, only with an explicit independent draw."""
    from .network_query_binding import RATE, read_rate
    if not independent_draw(text) or re.search(r'无放回|名额|分层|分组|邀请|可拒绝|自行决定', text):
        return None
    patterns = [r'(?:每|各)(?:个|家|位)?(?:站点|门店|单位|对象|节点|店|站|人)(?:均|都)?(?:以|按|有)('+RATE+r')(?:的)?(?:概率|机会)',
                r'(?:每|各).{0,14}分别抽签[，,]互不影响[，,][^。；]{1,20}的(?:概率|机会)(?:均|都)(?:为|是)('+RATE+r')']
    values = {read_rate(m[1]) for pattern in patterns for m in re.finditer(pattern, text)}
    if len(values) != 1:
        return None
    p = values.pop()
    # A contradictory named rate must not be hidden by a common-rate declaration.
    for node in nodes:
        hits = re.findall(re.escape(node)+r'(?:的)?(?:启用|开放|入选|中签)?(?:的)?(?:概率|机会)(?:为|是|等于)('+RATE+r')', text)
        if any(read_rate(v) != p for v in hits):
            return None
    return dict.fromkeys(nodes, str(p))


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
