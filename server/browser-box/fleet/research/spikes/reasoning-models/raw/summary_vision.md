| config | calls | HTTP/API errors | schema-valid | truncated (length) | correct (all tasks) | act+observe correct | extract mean | BU step | p50 s | p90 s | mean $/call | sum $ | providers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| glm-5.3-flash@low | 6 | 0 | 6/6 | 0 | 6.0/6 | - | 0.00 | - | 1.49 | 2.40 | 0.00045 | 0.0027 | Modal:3, Friendli:3 |
| REF-closed:gpt-6-luna@none | 6 | 0 | 3/6 | 0 | 3.0/6 | - | 0.00 | - | 2.05 | 2.21 | 0.00023 | 0.0014 | OpenAI:6 |
| gemma-4-31b@default | 6 | 0 | 6/6 | 0 | 1.0/6 | - | 0.00 | - | 4.09 | 4.71 | 0.00032 | 0.0019 | DeepInfra:6 |
| deepseek-v4.1-flash@off | 6 | 0 | 6/6 | 0 | 1.8/6 | - | 0.00 | - | 1.23 | 1.60 | 0.00025 | 0.0015 | DigitalOcean:3, InferenceNet:1, Morph:1, Ionstream:1 |
| mimo-v2.6-flash@off | 6 | 0 | 6/6 | 0 | 5.0/6 | - | 0.00 | - | 4.03 | 5.69 | 0.00023 | 0.0014 | Xiaomi:6 |
| qwen3.8-flash@off | 6 | 0 | 5/6 | 0 | 3.0/6 | - | 0.00 | - | 8.39 | 11.72 | 0.00032 | 0.0019 | Alibaba:6 |

Per task: correct/runs (p50 latency s)
| config | v_click_coords | v_extract_ratings |
|---|---|---|
| glm-5.3-flash@low | 3/3 (1.1) | 3/3 (2.1) |
| REF-closed:gpt-6-luna@none | 0/3 (2.2) | 3/3 (1.9) |
| gemma-4-31b@default | 0/3 (3.2) | 1/3 (4.3) |
| deepseek-v4.1-flash@off | 0/3 (1.6) | 1.8/3 (1.1) |
| mimo-v2.6-flash@off | 2/3 (5.2) | 3/3 (2.4) |
| qwen3.8-flash@off | 0/3 (10.6) | 3/3 (4.8) |

Failures (invalid, truncated, wrong, or errors):
- gemma-4-31b@default v_click_coords r0: status=200 prov=DeepInfra finish=stop valid=True parse=direct note=(882,748) pixel_hit=False norm1000_hit=False err=
- deepseek-v4.1-flash@off v_click_coords r2: status=200 prov=InferenceNet finish=stop valid=True parse=direct note=(887,767) pixel_hit=False norm1000_hit=True err=
- gemma-4-31b@default v_click_coords r2: status=200 prov=DeepInfra finish=stop valid=True parse=direct note=(882,748) pixel_hit=False norm1000_hit=False err=
- gemma-4-31b@default v_extract_ratings r0: status=200 prov=DeepInfra finish=stop valid=True parse=direct note=[3, 4, 3, 5] err=
- deepseek-v4.1-flash@off v_click_coords r1: status=200 prov=Morph finish=stop valid=True parse=direct note=(1138,770) pixel_hit=False norm1000_hit=False err=
- REF-closed:gpt-6-luna@none v_click_coords r1: status=200 prov=OpenAI finish=stop valid=False parse=lenient note=(1137,790) pixel_hit=True norm1000_hit=False err=
- gemma-4-31b@default v_click_coords r1: status=200 prov=DeepInfra finish=stop valid=True parse=direct note=(882,748) pixel_hit=False norm1000_hit=False err=
- deepseek-v4.1-flash@off v_extract_ratings r1: status=200 prov=DigitalOcean finish=stop valid=True parse=direct note=[2, 0, 0, 4] err=
- deepseek-v4.1-flash@off v_click_coords r0: status=200 prov=Ionstream finish=stop valid=True parse=direct note=(1138,770) pixel_hit=False norm1000_hit=False err=
- REF-closed:gpt-6-luna@none v_click_coords r2: status=200 prov=OpenAI finish=stop valid=False parse=lenient note=(1137,790) pixel_hit=True norm1000_hit=False err=
- REF-closed:gpt-6-luna@none v_click_coords r0: status=200 prov=OpenAI finish=stop valid=False parse=lenient note=(1137,790) pixel_hit=True norm1000_hit=False err=
- qwen3.8-flash@off v_click_coords r0: status=200 prov=Alibaba finish=stop valid=False parse=direct note=score error TypeError: list indices must be integers or slices, not str err=[{'type': 'object', 'properties': {'x': 887, 'y': 769}, 'required': ['x', 'y'], 'additionalProperties': False}] is not of type 'object'
- deepseek-v4.1-flash@off v_extract_ratings r0: status=200 prov=DigitalOcean finish=stop valid=True parse=direct note=[2, 3, 1, 4] err=
- gemma-4-31b@default v_extract_ratings r2: status=200 prov=DeepInfra finish=stop valid=True parse=direct note=[3, 4, 3, 5] err=
- mimo-v2.6-flash@off v_click_coords r0: status=200 prov=Xiaomi finish=stop valid=True parse=direct note=(887,774) pixel_hit=False norm1000_hit=True err=
- gemma-4-31b@default v_extract_ratings r1: status=200 prov=DeepInfra finish=stop valid=True parse=direct note=[3, 1, 2, 5] err=
- qwen3.8-flash@off v_click_coords r2: status=200 prov=Alibaba finish=stop valid=True parse=direct note=(887,769) pixel_hit=False norm1000_hit=True err=
- qwen3.8-flash@off v_click_coords r1: status=200 prov=Alibaba finish=stop valid=True parse=direct note=(887,769) pixel_hit=False norm1000_hit=True err=

total calls 36, total usage.cost $0.0108
