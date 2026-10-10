| run | model | task | correct | steps | LLM calls | LLM s | wall s | $ | length | providers | final answer (start) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ds_d_1 | deepseek/deepseek-v4.1-flash | d | True | 4 | 3 | 8.9 | 47.1 | 0.0015 | 0 | InferenceNet, Wafer | After navigating to https://the-internet.herokuapp.com/dynamic_loading/2, clicking the Start button, and waiting for the |
| ds_d_2 | deepseek/deepseek-v4.1-flash | d | True | 5 | 4 | 7.4 | 50.2 | 0.00633 | 0 | CoreWeave, Makora | The exact text that appears after clicking Start on https://the-internet.herokuapp.com/dynamic_loading/2 and waiting for |
| ds_d_3 | deepseek/deepseek-v4.1-flash | d | True | 6 | 5 | 9.2 | 64.3 | 0.005 | 0 | CoreWeave, Makora, Morph | After navigating to https://the-internet.herokuapp.com/dynamic_loading/2, clicking the Start button, and waiting for the |
| ds_q_1 | deepseek/deepseek-v4.1-flash | q | True | 4 | 3 | 7.8 | 29.6 | 0.00321 | 0 | CoreWeave, Wafer | The author of the first quote on page 3 is Pablo Neruda. The quote reads: "I love you without knowing how, or when, or f |
| ds_q_2 | deepseek/deepseek-v4.1-flash | q | True | 6 | 5 | 9.0 | 95.3 | 0.00169 | 0 | CoreWeave, InferenceNet | The author of the first quote on page 3 is Pablo Neruda. The quote is: 'I love you without knowing how, or when, or from |
| ds_q_3 | deepseek/deepseek-v4.1-flash | q | True | 4 | 3 | 8.6 | 27.4 | 0.00334 | 0 | CoreWeave, Morph | The author of the first quote on page 3 of quotes.toscrape.com is Pablo Neruda. |
| glm_d_1 | z-ai/glm-5.3-flash | d | True | 4 | 3 | 12.9 | 49.2 | 0.00295 | 0 | Friendli, Parasail, Together | The exact text that appears after clicking Start and waiting on https://the-internet.herokuapp.com/dynamic_loading/2 is: |
| glm_d_2 | z-ai/glm-5.3-flash | d | True | 4 | 3 | 17.2 | 52.2 | 0.00285 | 0 | Fireworks, Parasail | On https://the-internet.herokuapp.com/dynamic_loading/2, after clicking the Start button and waiting for loading to fini |
| glm_d_3 | z-ai/glm-5.3-flash | d | True | 4 | 3 | 5.0 | 31.9 | 0.00225 | 0 | BaseTen, Friendli, Parasail | The exact text that appears after loading is: "Hello World!" |
| glm_q_1 | z-ai/glm-5.3-flash | q | True | 4 | 3 | 6.1 | 33.4 | 0.00282 | 0 | Friendli, Inceptron, Together | The author of the first quote on page 3 of quotes.toscrape.com is Pablo Neruda. (Quote: "I love you without knowing how, |
| glm_q_2 | z-ai/glm-5.3-flash | q | True | 4 | 3 | 4.3 | 39.7 | 0.00205 | 0 | BaseTen, Friendli, Together | The author of the first quote on page 3 of https://quotes.toscrape.com/ is Pablo Neruda. The quote: "I love you without  |
| glm_q_3 | z-ai/glm-5.3-flash | q | True | 4 | 3 | 5.2 | 27.7 | 0.0015 | 0 | Fireworks, InferenceNet | The first quote on page 3 of quotes.toscrape.com is: "I love you without knowing how, or when, or from where..." and its |

- deepseek/deepseek-v4.1-flash: 6/6 correct, median steps 4.5, median LLM time 8.75 s, median wall 48.650000000000006 s, total $0.0211
- z-ai/glm-5.3-flash: 6/6 correct, median steps 4.0, median LLM time 5.65 s, median wall 36.55 s, total $0.0144
