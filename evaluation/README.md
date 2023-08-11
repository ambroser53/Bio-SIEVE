# Evaluation

All models are evaluated by passing the relevant set through `generate_cli.py` which generates a `.jsonl` file containing the predictions for each sample in the dataset. The predictions are then evaluated using the `evaluate.py` script which calculates the metrics for each task.

```bash
python generate_cli.py \
    --lora_weights <model path> \
    --dataset ../data/<dataset> \
    --num_beams 4 \
    --output_file <output path>

python evaluate.py \
    --results_path <output path> \
    --dataset_path ../data/<dataset> \
    --label_field_name <label field name> \ # gold_label for safety-first, output otherwise
    --lines \
    --rogue_tokens
```

A classification report will be produced providing include and exclude precision, recall and F-1 along with macro performance.

```<dataset>``` files must be in ```.json``` format with keys: ```instruction```, ```input``` and (when training or evaluating) ```output```.

For ```instruction``` use the following for each task:

- Include/Exclude: "Given the abstract, objectives and selection criteria should the study be included or excluded?"

(Multi models only)

- Exclusion Reasoning: "The given abstract has been excluded from this review with the following objectives and selection criteria. Provide an explanation for why the abstract was excluded."
- Population Extraction: "Given the abstract, what is the study's Population?"
- Intervention Extraction: "Given the abstract, what is the study's Intervention?"
- Outcome Extraction: "Given the abstract, what is the study's Outcome?"

For ```input``` use the following format:
- Include/Exclude/Reasoning: ```Abstract: <x> Objectives: <y> Selection Criteria: z```
- PIO Extraction: ```Abstract: <x>```
