# 文献案例 LLM 评测底座

这里不调用任何 API，只提供可复跑的导出与评分接口。

当前接口需要实际逐问结果、输入文件摘要和独立语义评审；下方旧例仅用于理解历史记录，单靠通过标记已经不能得分。详见 [当前评测口径](../CURRENT_EVALUATION_ZH.md)。

## 文件

```text
cases.jsonl                          63 条公开输入（模型可见，不含答案）
schema.json                          单次尝试的 JSONL 字段
../research_only/benchmark/references.jsonl   63 条参考答案索引（禁止给模型）
../tools/export_benchmark.py         重新导出 cases/references
../tools/score_benchmark.py          对记录的 attempts 评分
```

## 使用

```powershell
python -m evaluation.literature_cases.tools.export_benchmark
python -m evaluation.literature_cases.tools.score_benchmark --attempts attempts.jsonl --output score.json
```

`attempts.jsonl` 的旧记录示例（现在缺少证据，不能通过）：

```json
{"case_id":"LIT-NET-01","variant":"original","run_id":"r1","model":"deepseek","prompt_version":"v1","transport_complete":true,"contract_passed":true,"query_count":3,"semantic_passed":true,"expected_decision_passed":true,"point_present":true,"point_replay_passed":true}
```

评分分开报告：

- 传输失败；
- JSON/合同失败；
- 语义读取失败；
- 预期识别状态失败；
- 证书重放失败；
- PASS_RECORDED_EVIDENCE（保存的证据与评审通过检查，不代表本评分器重新证明结论）。

新记录还必须包含 `input_sha256`、`query_results` 和 `semantic_review`，具体字段见 schema.json。逐问保留识别器的实际 result；停止结果要说明是否因正确原因停止。POINT 与 PARTIAL 均核对证书和实际执行记录。损坏的 JSONL 行计作失败，不中断整批评分。参考答案不能返回被测模型。

并分开统计 development 与 holdout。  
API Key 只走环境变量或受控本地配置，不写入仓库。
