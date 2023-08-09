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