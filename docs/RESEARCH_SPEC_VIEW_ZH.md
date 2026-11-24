# 内部研究模型与查看工具：使用和边界

内部模型：[research_spec_model.py](../cfm_id/research_spec_model.py)；共享定义：[research_spec_catalog.py](../cfm_id/research_spec_catalog.py)；查看工具：[research_spec_view.py](../cfm_id/research_spec_view.py)。查看工具从内部模型渲染，不另造六项分类。它不调用 LLM、审核人或求解器，不接管默认网页；内部属性也不能当批准票据直接执行。

## 保留与归类

原 JSON 保存为不可变文本；每个值带原字段的 JSON Pointer。查看时按六项归类，来源、共同定义、原未知项和视图尚未归类的字段分别列出。未归类是视图的覆盖限制，不自动表示用户资料缺失。

分配项分开显示原模板、分组、名额、概率、阶段和接受规则。目标保留两端顺序、评价范围、背景与平均方式。暴露保留原模板和参数，不擅自变换阈值。尚未决定、不采用、明确额外限制及空列表均保持原值。

视图没有将含混的背景字符串拆成已批准的时期或条件；没有通过自然语言判断来源是否真正支持参数；没有补齐旧记录未填写的内容。已登记 D/E 模板可以展开为描述属性；设计支持、暴露值和边界计算继续由原库负责。

## Python 使用

```python
from cfm_id.research_spec_view import build_view, from_json, to_html

# 已经按原接口保存的 JSON 字典。
view = build_view(existing_record, contract="network-facts")
assert view.original_record() == existing_record
view.assert_current(existing_record)  # 对应原记录有变化时拒绝继续用旧视图

# 旧解析、审核和执行继续消费 existing_record；不消费 view.as_dict()。
display = view.as_dict()
assert display["executable"] is False
assert display["is_approval"] is False

# 若有原 JSON 文本，保留其空白、键顺序和数值写法。
view = from_json(saved_json_text, contract="network-facts")
assert view.record_json == saved_json_text
html_page = to_html(view)
```

可以显式附带 `review=` 和 `result=`，它们只原样保存、展示，不能代替原审核和证书验证。所有输入必须已是严格 JSON；原生 dataclass、tuple、Fraction 或 Pydantic 对象，应先由其既有持久化协议序列化。视图不会自行选择新的科学摘要算法或数值转换规则。

支持的显式格式：`direct`、`compact`、`network-facts`、`dag-facts`、`mean-order`、`native-study`、`native-target`、`dag-problem`、`iv-problem`、`bounded-information`。这些是查看适配，不是数学能力清单；选择一种格式也不表示记录通过该格式的原验证器。

属性对应阶段另加入 `policy-materials`、`direct-report`、`policy-packet`、`math-request`。其中 `math-request` 只展开已有的 `causal-id.math-request/1` 及登记的 12 类原生操作、6 条研究路线。未知版本或操作保留原问题，不猜测归属。来源、原审核、原结果、方法标识和交接权限各自列出；材料中的条件性计算不会被当成研究者批准。

默认直答的 `status/functional/value` 与六项输入分开，标注为模型原答。逐问题的 `answers` 也按原索引保留，不把多个目标合成一个。网络事实适配覆盖公共字段；专门扩展字段没有规则时进入“未归类”，完整原记录仍保存。

## 属性展开和还原比对

面向后续内部开发，使用有版本的模型：

```python
from cfm_id.research_spec_model import build_internal_study

study = build_internal_study(view)
for design in study.for_facet("assignment"):
    design.property("joint_law")
    design.property("stratification")
original_input = study.to_legacy()
```

六项各有明确属性；多目标和多个信息对象保留各自原对象位置。模板给出的确定性含义与尚未解释的原表达分别标记。每个原字段只有一份权威值，其他属性引用它；模型名称、方法编号不用于推断遗漏的条件。直接篡改内部描述后，`to_legacy()` 会拒绝沿用旧输入执行，必须更改原规格并重新建立对应，旧审核也不能自动迁移。

下层投影用于兼容诊断：

```python
from cfm_id.research_spec_projection import expand

projection = expand(view)
attributes = projection.attributes  # 有旧定义依据的描述属性
issues = projection.issues          # 未展开、未知或需回原文核对的项目
restored = projection.restore_legacy()
assert projection.compare(existing_record)["equivalent"]
```

还原使用带原路径的分类字段及容器结构，不通过暗存一份原值来绕过检查。名单/数组顺序、空对象、空数组、null、布尔与数值类型保留；缺失、重复或额外的字段槽会被拒绝。`compare` 返回变动位置，可核对目标、权重、限制等是否被更改。原 JSON 的空白、数值写法和原始字节仍由 `view.record_json` 保存，投影还原不承诺重新生成相同字节。

`research-spec-projection-1` 不是新 LLM Schema，也不能作为执行或审核票据。展示属性不参与还原和方法选择；改动属性说明不会自动改变执行输入。比对证明的是旧 JSON 值及其原合同保留，不能证明任意自然语言或未来新合同与原意相同。模板缺参数提示只检查部分必要字段，完整合法性仍由原接口判断。

## 本地导出 HTML

在个人仓库根目录（开发目录则进入 `identification`）运行：

```powershell
python -m cfm_id.research_spec_view saved_record.json --contract network-facts --html six_facets.html
```

不带 `--html` 时输出视图 JSON。导出的页面没有批准或执行按钮，没有远程资源和脚本，原文经过 HTML 转义。不得将视图的 `snapshot_sha256` 写入旧科学审核的 hash 字段：它只标记这个显示快照。

## 本轮验收的含义

[针对性测试](../tests_gateway/test_research_spec_view.py)核对：

- 原记录不变、返回对象与输入相互隔离；缺字段、null、空容器以及 bool/int/float 不混同；重复 JSON 键和非有限数值拒绝处理。
- 紧凑读取同题的两种 POINT 方法仍得到相同结果和估计交接，原证书重放通过；未审或改变目标后不能沿用审核。
- D1–D8 的八个固定配对覆盖 E1–E5：原目标、条件、支持概率、数值界及证书保持一致。这不是重新穷举全部 D×E 组合。
- 均值顺序的三组条件、DAG 的符号公式和 IV 的结果保持一致并经过原入口重放。
- 真正额外限制、信息完整性未决定以及 D6 排除限制不采用等状态，仍按原规则停止，不由视图补全。
- E1 的平票/孤立点和 E2 的阈值/未定义情况交回原实现计算。

测试是已保存规格的兼容验收，不是新业务的 LLM 阅读测评，也不表示网页所有入口已经改用六项合同。本次没有进行这种替换。

第三步补充的[属性兼容测试](../tests_gateway/test_research_spec_compatibility.py)和实际范围见[属性对应与兼容验收](RESEARCH_SPEC_COMPATIBILITY_ZH.md)。所有导出都用于本地查看，不包含新的执行入口。

后续的[固定政策](RESEARCH_SPEC_POLICY_EXECUTION_ZH.md)、[随机化局部效应](RESEARCH_SPEC_LOCAL_EXECUTION_ZH.md)和[观察性目标](RESEARCH_SPEC_OBSERVATIONAL_EXECUTION_ZH.md)已经接到各自的实际构造链路。它们不通过此视图的 `to_legacy()` 执行，也不把只读 HTML 变为批准或运行入口。哪些入口保留专用实现见[维护清单](RESEARCH_SPEC_ENTRY_STATUS_ZH.md)。
