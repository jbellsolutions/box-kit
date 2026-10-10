| config | calls | HTTP/API errors | schema-valid | truncated (length) | correct (all tasks) | act+observe correct | extract mean | BU step | p50 s | p90 s | mean $/call | sum $ | providers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| deepseek-v4.1-flash@off | 27 | 0 | 27/27 | 0 | 26.0/27 | 17.0/18 | 1.00 | 3.0/3 | 1.09 | 2.11 | 0.00063 | 0.0171 | CoreWeave:15, DigitalOcean:3, InferenceNet:3, Together:3 |
| gemma-4-31b@default | 27 | 0 | 25/27 | 2 | 25.0/27 | 16.0/18 | 1.00 | 3.0/3 | 4.34 | 20.40 | 0.00067 | 0.0181 | DeepInfra:27 |
| glm-5.3-flash@high | 52 | 0 | 51/52 | 1 | 51.0/52 | 37.0/38 | 1.00 | 8.0/8 | 1.48 | 3.69 | 0.00061 | 0.0317 | Friendli:15, Modal:12, Together:12, Parasail:9 |
| mistral-small-2603@none | 27 | 20 | 7/27 | 0 | 7.0/27 | 7.0/18 | 0.00 | 0.0/3 | 1.13 | 1.54 | 0.00054 | 0.0038 | Mistral:7 |
| qwen3.8-flash@off | 27 | 0 | 27/27 | 0 | 27.0/27 | 18.0/18 | 1.00 | 3.0/3 | 2.43 | 8.88 | 0.00041 | 0.0112 | Alibaba:27 |
| gpt-oss-120b@low | 27 | 0 | 27/27 | 0 | 25.0/27 | 18.0/18 | 0.67 | 3.0/3 | 3.02 | 9.84 | 0.00028 | 0.0076 | DekaLLM:8, AkashML:7, CoreWeave:4, DeepInfra:3 |
| deepseek-v4.1-flash@low | 27 | 0 | 27/27 | 0 | 25.0/27 | 16.0/18 | 1.00 | 3.0/3 | 2.11 | 5.62 | 0.00081 | 0.0220 | CoreWeave:15, DigitalOcean:3, Modal:3, InferenceNet:3 |
| mimo-v2.6-flash@off | 27 | 0 | 27/27 | 0 | 23.0/27 | 14.0/18 | 1.00 | 3.0/3 | 4.69 | 14.84 | 0.00034 | 0.0093 | Xiaomi:26, Io Net:1 |
| REF-closed:gpt-6-luna@none | 27 | 6 | 20/27 | 0 | 20.0/27 | 18.0/18 | 0.00 | 2.0/3 | 1.23 | 2.25 | 0.00028 | 0.0059 | OpenAI:21 |
| nemotron-3.5-lightning@off | 27 | 0 | 27/27 | 0 | 24.0/27 | 15.0/18 | 1.00 | 3.0/3 | 0.95 | 2.46 | 0.00031 | 0.0085 | DeepInfra:15, Io Net:6, CoreWeave:5, Phala:1 |
| glm-5.3-flash@low | 72 | 0 | 70/72 | 2 | 67.0/72 | 48.0/53 | 1.00 | 8.0/8 | 1.36 | 3.46 | 0.00050 | 0.0361 | Friendli:27, Together:16, Parasail:14, Modal:12 |
| glm-5.3-flash@low-t0 | 20 | 0 | 19/20 | 1 | 19.0/20 | 14.0/15 | 1.00 | - | 1.90 | 9.07 | 0.00052 | 0.0104 | Friendli:10, Parasail:5, Together:5 |

Per task: correct/runs (p50 latency s)
| config | sh_act_dropdown | sh_act_negative | sh_extract_books | sh_act_type | sh_observe_categories | sh_act_sharp_basket | bu_step_poetry | sh_act_book_link | sh_extract_quotes |
|---|---|---|---|---|---|---|---|---|---|
| deepseek-v4.1-flash@off | 3/3 (1.3) | 3/3 (1.0) | 3/3 (2.1) | 3/3 (1.0) | 3/3 (0.9) | 2/3 (0.8) | 3/3 (1.5) | 3/3 (0.9) | 3/3 (2.1) |
| gemma-4-31b@default | 3/3 (3.3) | 3/3 (1.2) | 3/3 (18.8) | 1/3 (347.2) | 3/3 (4.3) | 3/3 (3.1) | 3/3 (16.1) | 3/3 (3.0) | 3/3 (16.7) |
| glm-5.3-flash@high | 8/8 (1.6) | 3/3 (0.9) | 3/3 (2.7) | 3/3 (0.8) | 8/8 (1.1) | 7/8 (1.0) | 8/8 (2.4) | 8/8 (1.4) | 3/3 (1.6) |
| mistral-small-2603@none | 1/3 (1.2) | 1/3 (2.1) | 0/3 (err) | 3/3 (0.9) | 0/3 (err) | 1/3 (1.2) | 0/3 (err) | 1/3 (1.1) | 0/3 (err) |
| qwen3.8-flash@off | 3/3 (2.2) | 3/3 (1.4) | 3/3 (7.4) | 3/3 (2.1) | 3/3 (2.4) | 3/3 (2.2) | 3/3 (3.7) | 3/3 (2.3) | 3/3 (6.4) |
| gpt-oss-120b@low | 3/3 (2.1) | 3/3 (1.1) | 2/3 (11.6) | 3/3 (3.3) | 3/3 (2.6) | 3/3 (2.5) | 3/3 (3.7) | 3/3 (2.1) | 2/3 (4.6) |
| deepseek-v4.1-flash@low | 3/3 (1.8) | 3/3 (1.7) | 3/3 (5.0) | 3/3 (2.1) | 3/3 (1.1) | 2/3 (2.1) | 3/3 (1.3) | 2/3 (3.1) | 3/3 (4.7) |
| mimo-v2.6-flash@off | 1/3 (8.1) | 3/3 (2.7) | 3/3 (14.8) | 2/3 (2.0) | 2/3 (2.3) | 3/3 (8.8) | 3/3 (4.7) | 3/3 (1.9) | 3/3 (13.6) |
| REF-closed:gpt-6-luna@none | 3/3 (1.0) | 3/3 (1.1) | 0/3 (err) | 3/3 (1.0) | 3/3 (1.7) | 3/3 (1.1) | 2/3 (2.3) | 3/3 (1.3) | 0/3 (err) |
| nemotron-3.5-lightning@off | 3/3 (0.7) | 1/3 (0.7) | 3/3 (2.8) | 3/3 (0.6) | 2/3 (1.0) | 3/3 (0.9) | 3/3 (2.2) | 3/3 (0.9) | 3/3 (1.4) |
| glm-5.3-flash@low | 7/8 (1.1) | 3/3 (1.6) | 3/3 (3.3) | 3/3 (0.5) | 13/13 (1.0) | 10/13 (1.1) | 8/8 (1.8) | 12/13 (0.7) | 8/8 (2.2) |
| glm-5.3-flash@low-t0 | - | - | - | - | 5/5 (1.0) | 5/5 (7.8) | - | 4/5 (0.9) | 5/5 (2.3) |

Failures (invalid, truncated, wrong, or errors):
- mistral-small-2603@none sh_extract_books r0: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- REF-closed:gpt-6-luna@none sh_extract_quotes r0: status=400 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 400, "metadata": {"raw": "{\n  \"error\": {\n    \"message\": \"Invalid schema for response_format 'Extraction': 
- mimo-v2.6-flash@off sh_act_type r1: status=200 prov=Xiaomi finish=stop valid=True parse=direct note=null err=
- mistral-small-2603@none sh_extract_books r1: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mimo-v2.6-flash@off sh_observe_categories r0: status=200 prov=Xiaomi finish=stop valid=True parse=direct note=junk click args ['Poetry'] err=
- deepseek-v4.1-flash@low sh_act_book_link r0: status=200 prov=DigitalOcean finish=stop valid=True parse=direct note=null err=
- glm-5.3-flash@low sh_act_book_link r1: status=200 prov=Together finish=length valid=False parse=fail note=unparsable err=
- mistral-small-2603@none sh_extract_quotes r0: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mistral-small-2603@none sh_observe_categories r2: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- gpt-oss-120b@low sh_extract_quotes r2: status=200 prov=CoreWeave finish=stop valid=True parse=direct note=0/10 matched, 1 returned err=
- deepseek-v4.1-flash@off sh_act_sharp_basket r1: status=200 prov=Together finish=stop valid=True parse=direct note=null err=
- nemotron-3.5-lightning@off sh_act_negative r1: status=200 prov=DeepInfra finish=stop valid=True parse=direct note=0-1662/click err=
- nemotron-3.5-lightning@off sh_act_negative r2: status=200 prov=DeepInfra finish=stop valid=True parse=direct note=0-1669/click err=
- mistral-small-2603@none sh_act_sharp_basket r2: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- REF-closed:gpt-6-luna@none sh_extract_books r2: status=400 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 400, "metadata": {"raw": "{\n  \"error\": {\n    \"message\": \"Invalid schema for response_format 'Extraction': 
- mistral-small-2603@none sh_extract_quotes r1: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mistral-small-2603@none sh_act_negative r0: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mistral-small-2603@none sh_act_dropdown r1: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mistral-small-2603@none sh_act_sharp_basket r0: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- REF-closed:gpt-6-luna@none sh_extract_quotes r2: status=400 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 400, "metadata": {"raw": "{\n  \"error\": {\n    \"message\": \"Invalid schema for response_format 'Extraction': 
- mistral-small-2603@none bu_step_poetry r2: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mistral-small-2603@none bu_step_poetry r0: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- glm-5.3-flash@low sh_act_dropdown r1: status=200 prov=Modal finish=stop valid=True parse=direct note=null err=
- REF-closed:gpt-6-luna@none sh_extract_quotes r1: status=400 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 400, "metadata": {"raw": "{\n  \"error\": {\n    \"message\": \"Invalid schema for response_format 'Extraction': 
- mimo-v2.6-flash@off sh_act_dropdown r1: status=200 prov=Xiaomi finish=stop valid=True parse=direct note=null err=
- glm-5.3-flash@low sh_act_sharp_basket r1: status=200 prov=Friendli finish=length valid=False parse=fail note=unparsable err=
- REF-closed:gpt-6-luna@none sh_extract_books r0: status=400 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 400, "metadata": {"raw": "{\n  \"error\": {\n    \"message\": \"Invalid schema for response_format 'Extraction': 
- REF-closed:gpt-6-luna@none bu_step_poetry r2: status=200 prov=OpenAI finish=stop valid=False parse=fail note=unparsable err=
- REF-closed:gpt-6-luna@none sh_extract_books r1: status=400 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 400, "metadata": {"raw": "{\n  \"error\": {\n    \"message\": \"Invalid schema for response_format 'Extraction': 
- mistral-small-2603@none sh_observe_categories r0: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mistral-small-2603@none sh_act_book_link r1: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mistral-small-2603@none sh_act_dropdown r0: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- deepseek-v4.1-flash@low sh_act_sharp_basket r1: status=200 prov=Together finish=stop valid=True parse=direct note=null err=
- mistral-small-2603@none sh_act_book_link r0: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mistral-small-2603@none bu_step_poetry r1: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- gpt-oss-120b@low sh_extract_books r2: status=200 prov=CoreWeave finish=stop valid=True parse=direct note=0/20 matched, 2 returned err=
- mistral-small-2603@none sh_extract_quotes r2: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mistral-small-2603@none sh_observe_categories r1: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mistral-small-2603@none sh_extract_books r2: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mistral-small-2603@none sh_act_negative r2: status=429 prov=None finish=None valid=False parse=None note= err={"message": "Provider returned error", "code": 429, "metadata": {"raw": "mistralai/mistral-small-2603 is temporarily rate-limited upstream. Please retry shortly
- mimo-v2.6-flash@off sh_act_dropdown r2: status=200 prov=Xiaomi finish=stop valid=True parse=direct note=0-117/selectOptionFromDropdown/['Option 2'] err=
- nemotron-3.5-lightning@off sh_observe_categories r1: status=200 prov=Io Net finish=stop valid=True parse=direct note=0-173,0-91 err=
- gemma-4-31b@default sh_act_type r0: status=200 prov=DeepInfra finish=length valid=False parse=fail note=unparsable err=
- gemma-4-31b@default sh_act_type r1: status=200 prov=DeepInfra finish=length valid=False parse=fail note=unparsable err=
- glm-5.3-flash@low sh_act_sharp_basket r0: status=200 prov=Friendli finish=stop valid=True parse=direct note=junk click args ['],', 'twoStep}} 2:false} jedoch', 'twoStep'] err=
- glm-5.3-flash@low-t0 sh_act_book_link r0: status=200 prov=Together finish=length valid=False parse=fail note=unparsable err=
- glm-5.3-flash@low sh_act_sharp_basket r2: status=200 prov=Friendli finish=stop valid=True parse=direct note=junk click args ['LEFT'] err=
- glm-5.3-flash@high sh_act_sharp_basket r2: status=200 prov=Friendli finish=length valid=False parse=fail note=unparsable err=

total calls 387, total usage.cost $0.1816
