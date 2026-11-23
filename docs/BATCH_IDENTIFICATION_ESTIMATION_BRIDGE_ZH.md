# — Batch Identification 与现有 ER300 Estimation 桥接

## 范围与约束

这里的桥接检验既有识别请求与批量证明的目标、设计和支持一致性。个人仓库的运行边界是可重放的识别与查询交接。

### 1. 已确认新 family 单 arm → 全节点 arm 证明网格

```python
from pfn_pipeline import (
    identify_randomized_network_batch, make_heterogeneous_bernoulli_arm_task,
    replay_network_arm_batch,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec

# net: 已经从正式研究协议确认的 NetworkExposureSpec
seed_task = make_heterogeneous_bernoulli_arm_task(
    net, propensities={node: "1/2" for node in net.node_ids},
    node_id=net.node_ids[0], own_treatment_value=0, exposure_value=0,
    source="actual declared protocol", evidence="documented evidence",
    admitted=True, query_authority="HUMAN_CONFIRMED",
)
batch = identify_randomized_network_batch(seed_task)
replay_network_arm_batch(batch)
print(batch.shape)                  # [N, 2, 2] 或 [N, 2, 3]
print(batch.coverage_status)       # ALL_POINT_IDENTIFIED / SOME_ARMS_UNSUPPORTED
print(batch.cell(net.node_ids[0], 0, 0))
assert batch.estimation_request is None
```

- 支持已实现 D1/D2/D3 × E1/E2/E3；原论文/定理前提由已验证的正式 seed 承接，**不通过观测样本补认假设**。入口要求选作锚点的那个单 arm 已有正 support 且 `POINT/VERIFIED`；若锚点本身为零 support，需要在**同一研究规格下**换一个有正 support 的锚点，不能推断“其他所有 arm 都不支持”。
- 返回每 arm `status`（POINT 或 UNSUPPORTED）、`reason_code`、精确 `joint_support`（有理数字符串；E2 孤立节点为 `None`）、`target_fingerprint`、整体 `batch_sha256`。
- 状态 `SOME_ARMS_UNSUPPORTED` 只表示某些查询无定义或零 support，**不是数学上的 PARTIAL identification**。
- 全网络 `[N,2,S]` 是查询坐标形状，不是 `μ` 的预测数值，也不意味着 PFN 支持动态 S。
- v1.0 不提供任意表格/任意 DAG/任意 q,g；网络必须符合已实现的固定网络 family 与资源上限。

### 2. 同一个 ER300 legacy TaskSpec 的安全 bridge

```python
from pfn_pipeline import (
    identify, bind_legacy_response_batch,
    replay_legacy_response_batch_bridge,
)

# legacy_task 由调用方按已审核方案提供，是原有 ER300 多数响应评分任务。
legacy_id = identify(legacy_task)       # 已有 NETWORK_MAJORITY_RESPONSE_POLICY_SCORE
link = bind_legacy_response_batch(legacy_id)
replay_legacy_response_batch_bridge(link)
assert link.batch.coverage_status == "ALL_POINT_IDENTIFIED"
assert link.batch.shape == (300, 2, 2)
request = link.legacy_identification.estimation_request
```

Bridge 严格从 **同一个 replay-verified legacy TaskSpec** 中导出新的形式化 seed，逐 arm 与旧响应证书的联合设计 support 对拍，并绑定旧规格的 fingerprint。它**不生产新 EstimationRequest**，只在确认数学一致后复用**原始已验证四臂 response request**。所生成的 `link.batch` 本身仍是 population-only，无估计请求。

个人版的 `estimate_bound_legacy_response` 先重放绑定。对合法的请求，它会明确提示到完整 autoCFM 工程执行拟合。

旧拟合演示、checkpoint 和完整估计流程的接口说明见[原版本](https://github.com/zzyyLOGIC/CFM-identification/tree/cb322b4061fe981a8b5fd6fbd39660209c433911).

### 3. 为何没有直接把新 batch 变成 PFN 请求？

- 旧 PFN `predict` 接受 iid Bernoulli(1/2)、E1、连续 outcome、已知事实 `X,T,Y,A` 和四臂 `[N,2,2]`。
- 新 batch 用同一个 `q,g,W` 组织数学证明，但若由另一研究规格独立构造，不能只比较网络、`p` 和数组形状就宣称其条件背景 `W` 已经相同。
- D2/D3 配额、异质 p_i、E2/E3 可能改变目标权重或 arm 坐标，还没有匹配的训练标签/模型；应报告 `NO_ADAPTER`。
- Policy 使用四臂代理评分不等于固定完整分配下真实 rollout welfare；本次不改变 Policy 语义。

### 4. 验证方法

```bash
python -B -m unittest discover -s tests -p "test_batch_identification.py" -v
python -B -m unittest discover -s tests -p "test_*.py" -q
```

历史 ER300 批量演示见[旧版脚本](https://github.com/zzyyLOGIC/CFM-identification/tree/cb322b4061fe981a8b5fd6fbd39660209c433911/examples/run_batch_identification_and_legacy_bridge.py)。
