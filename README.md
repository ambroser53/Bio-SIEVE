# Bio-SIEVE

[Arxiv](https://arxiv.org/abs/2308.06610)

## Abstract

Medical systematic reviews can be very costly and resource
intensive. We explore how Large Language Models (LLMs)
can support and be trained to perform literature screening
when provided with a detailed set of selection criteria. Specif-
ically, we instruction tune LLaMA and Guanaco models to
perform abstract screening for medical systematic reviews.
Our best model, Bio-SIEVE, outperforms both ChatGPT and
trained traditional approaches, and generalises better across
medical domains. However, there remains the challenge of
adapting the model to safety-first scenarios. We also explore
the impact of multi-task training with Bio-SIEVE-Multi, in-
cluding tasks such as PICO extraction and exclusion rea-
soning, but find that it is unable to match single-task Bio-
SIEVE’s performance. We see Bio-SIEVE as an important
step towards specialising LLMs for the biomedical system-
atic review process and explore its future developmental op-
portunities. We release our models, code and a list of DOIs to
reconstruct our dataset for reproducibility.

## Models

The adapter weights for the 4 best models trained as part of this project can be found and used from HuggingFace:

| Model | Description | Link |
| --- | --- | --- |
| Guanaco7B (single) | Continuation of tuning the Guanaco7B adapter weights using include/exclude only samples from the dataset | [Link](https://huggingface.co/Ambroser53/Bio-SIEVE) |
| Guanaco7B (multi) | Continuation of tuning the Guanaco7B adapter weights using include/exclude, PICO samples and exclusion reasons from the dataset | [Link](https://huggingface.co/Ambroser53/Bio-SIEVE-Multi) |
| LLaMA7B (single) | Instruction tuned LLaMA7B using include/exclude only samples from the dataset | TBD |
| LLaMA7B (multi) | Instruction tuned LLaMA7B using include/exclude, PICO samples and exclusion reasons from the dataset | TBD |

## Dataset

Instruct Cochrane consists of 5 main splits as detailed in the table below:

| Task           | Train           | Test          | Subset        | Safety-First | Irrelevancy        |
|----------------|-----------------|---------------|---------------|------------------------|--------------|
| Inclusion      | 43,221           | 576           | 784           | 79                     | -            |
| Exclusion      | 44,879           | 425           | 927           | 29                     | 780          |
| **Inc/Exc**        | **88,100**          | **1,001**          | **1,711**          | **108**                    | **780**          |
| Population     | 15,501           | -             | -             | -                      | -            |
| Intervention   | 15,386           | -             | -             | -                      | -            |
| Outcome        | 15,518           | -             | -             | -                      | -            |
| Exc. Reason    | 11,204           | -             | -             | -                      | -            |
| 88Total8 | **168,842** | **1,001** | **1,711** | **108**          | **780** |

The dataset can be constructed from separate lists of DOIs, as described in `data/README.md`.

## Training

Models are all trained using a modified version of the [QLoRA](https://github.com/artidoro/qlora) training script ([Dettmers et. al.](https://arxiv.org/abs/2305.14314)). An example training script is found below with the necessary parameters to recreate out model from the dataset.

```bash
python qlora.py \
    --model_name_or_path elinas/llama-7b-hf-transformers-4.29 \
    --output_dir <output dir> \
    --dataset ./data/instruct_cochrane.json \
    --do_train True \
    --source_max_len 1024 \
    --target_max_len 384 \
    --per_device_train_batch_size 16 \
    --gradient_accumulation_steps 1 \
    --max_steps <max steps> \
    --data_seed 42 \
    --optim paged_adamw_32bit \
    --without_trainer_checkpoint True \
    --force_lora_training True \
    --report_to wandb \
```

## Evaluation

Models are evaluated on four datasets: Test, Subsets, Safety-First and Irrelevancy. 

Test evaluates the performance on the raw cochrane reviews. Subsets allow for comparison with logistic regression baselines as it allows for k-fold cross validation while training per review, simluating the existing active learning methods in literature. Safety-First better approximates the include/exclude process on just abstracts and titles. The test set is the final decision based on full-text screening, hence it is not always possible to derive their decision from the abstract and title alone. Irrelevancy is based on the subsets, wherein abstracts from completely different reviews are tested to evaluate whether the model can exclude samples far from the decision boundary.

Details on using the evaluations scripts can be found in `evaluation/README.md`.
