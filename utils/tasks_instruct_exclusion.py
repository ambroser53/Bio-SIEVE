import json
import os.path

import regex as re
from argparse import Namespace
from data_cleaning import remove_repeating_substrings

def pico_separate_look_multiple(args, examples, tokenizer, splitter_id, instruction_template_strs, prompt_templates, target_templates, alpaca_format_len):
    data = []

    instruction_templates = [[tokenizer.encode(a, max_length=args.max_input_length, padding=False, truncation=True) for a in
                         instruction_template.split('{}') if a] for instruction_template in instruction_template_strs]
    instruction_template_len_list = [sum([len(a) for a in instruction_template]) for instruction_template in instruction_templates]
    prompt_template = [tokenizer.encode(a, max_length=args.max_input_length, padding=False, truncation=True) for a in
                         prompt_templates.split('{}') if a][0]
    prompt_template_len = len(prompt_templates)
    target_templates = [[tokenizer.encode(a, max_length=args.max_input_length, padding=False, truncation=True) for a in
                         target_template.split('{}') if a] for target_template in target_templates]
    target_template_len_list = [sum([len(a) for a in target_template]) for target_template in target_templates]

    sections = ['Participants', 'Interventions', 'Outcomes']

    study_refs = []

    for example in examples:

        if 'references' in example:
            if 'References to studies included in this review' in example['references']:
                for reference in example['references']['References to studies included in this review']:

                    if "Study characteristics" in reference and any([key in reference['Study characteristics'] for key in
                            ['Participants', 'Interventions', 'Outcomes']]):
                        reference_info_key = 'Study characteristics'
                    elif 'Risk of bias' in reference and any([key in reference['Risk of bias'] for key in
                                                            ['Participants', 'Interventions', 'Outcomes']]):
                        reference_info_key = 'Risk of bias'
                    else:
                        continue

                    if args.ensure_no_pio_repeat:
                        # ensure no repeated references
                        study_ref = reference["id"].replace("{published data only}", "").replace("{published and unpublished data}", "").strip()
                        if study_ref in study_refs:
                            continue
                        else:
                            study_refs.append(study_ref)

                    study_pio_found = False
                    for study in reference['studies']:

                        if 'abstract' in study:
                            for section, instruction_template, target_template, instruction_template_len, target_template_len \
                                    in zip(sections, instruction_template_strs,
                                           target_templates,
                                           instruction_template_len_list,
                                           target_template_len_list):
                                if section not in reference[reference_info_key]:
                                    continue

                                abstract = dict_to_string(study['abstract']).replace(':', '')
                                if 'This CENTRAL record does not have an abstract.' in abstract or len(abstract) < 100:
                                    continue

                                abstract = clean_up(abstract, "abstract")

                                # for when the abstract is multilingual
                                if len(abstract.split(' Abstract ')) > 1:
                                    abstract = abstract.split(' Abstract ')[1]
                                new_inputs = [abstract]

                                new_input = get_tokens_splits(args, new_inputs, [prompt_template],
                                                              prompt_template_len, splitter_id, tokenizer,
                                                              instruction_template_len+alpaca_format_len)

                                new_targets = [reference[reference_info_key][section].replace(':', '')]
                                new_target = get_tokens_splits(args, new_targets, target_template,
                                                               target_template_len, splitter_id, tokenizer,
                                                               instruction_template_len+alpaca_format_len)
                                if new_input is not None and new_target is not None:
                                    data.append({
                                        'instruction': instruction_template,
                                        'input': post_clean_up(tokenizer.decode(new_input).replace('<s> ', ' ').strip()),
                                        'output': post_clean_up(tokenizer.decode(new_target).replace('<s> ', ' ').strip()),
                                        'topic': example['meta']['topic'],
                                        'ref_title': study['meta']['title'],
                                        'doi': example['id'],
                                    })
                                    study_pio_found = True

                        if study_pio_found:
                            break

    return data


def include_exclude(args, examples, tokenizer, splitter_id, instruction_template_str, prompt_template, target_template, alpaca_format_len):
    data = []

    # what kind of abstract sections DON'T we want to include in the prompt?
    abstract_section_filter = []

    inc_target = target_template[0]

    reason_instruction = "The given abstract has been excluded from this review with the following objectives and selection criteria." \
                         " Provide an explanation for why the abstract was excluded."
    explanation_instruction_template = [tokenizer.encode(a, max_length=args.max_input_length, padding=False, truncation=True) for a
                                        in reason_instruction.split('{}') if a]
    explanation_instruction_template_len = sum([len(a) for a in explanation_instruction_template])

    instruction_template = [tokenizer.encode(a, max_length=args.max_input_length, padding=False, truncation=True) for a in
                            instruction_template_str.split('{}') if a]
    instruction_template_len = sum([len(a) for a in instruction_template])
    prompt_template = [tokenizer.encode(a, max_length=args.max_input_length, padding=False, truncation=True) for a in
                       prompt_template.split('{}') if a]
    prompt_template_len = sum([len(a) for a in prompt_template])
    inc_target = tokenizer.encode(inc_target, max_length=args.max_input_length, padding=False, truncation=True)

    only_N = args.N != -1

    max_reasons = 0
    if args.always_reason:
        max_reasons_per_study = 100000
    else:
        max_reasons_per_study = 40
    n_reasons = 0

    for example in examples:
        n_current_review_samples = 0  # set to 0 for each review
        reason_next = False
        reasons_count = 0

        if args.doi is not None:
            if example['id'] != args.doi:
                continue

        if 'references' in example:
            includeds_key = None
            if 'References to studies included in this review' in example['references']:
                includeds_key = 'References to studies included in this review'
            elif 'References to included reviews' in example['references']:
                includeds_key = 'References to included reviews'

            if includeds_key is not None:
                for reference in example['references'][includeds_key]:
                    for study in reference['studies']:

                        # only do N samples per review ########
                        if only_N and n_current_review_samples >= args.N:
                            break
                        #######################################

                        if 'abstract' in study:
                            abstract = dict_to_string(study['abstract'], abstract_section_filter).replace(':', ' ')
                            if 'This CENTRAL record does not have an abstract.' in abstract or len(abstract) < 100:
                                continue

                            abstract = clean_up(abstract, "abstract")

                            # for when the abstract is multilingual
                            if len(abstract.split(' Abstract ')) > 1:
                                abstract = abstract.split(' Abstract ')[1]

                            if 'objectives' not in example["abstract"] or 'selection criteria' not in example["abstract"]:
                                continue

                            objectives = clean_up(example["abstract"]["objectives"], "objectives")
                            selection_criteria = clean_up(example["abstract"]["selection criteria"], "selection criteria")
                            new_inputs = [abstract, objectives, selection_criteria]

                            new_input = get_tokens_splits(args, new_inputs, prompt_template, prompt_template_len,
                                                          splitter_id, tokenizer, alpaca_format_len+instruction_template_len)
                            if new_input is not None:
                                data.append({
                                    'instruction': instruction_template_str,
                                    'input': post_clean_up(tokenizer.decode(new_input).replace('<s> ', ' ').strip()),
                                    'output': post_clean_up(tokenizer.decode(inc_target).replace('<s> ', ' ').strip()),
                                    'topic': example['meta']['topic'],
                                    'ref_title': study['meta']['title'],
                                    'doi': example['id'],
                                })
                                n_current_review_samples += 1

            excludeds_key = None
            if 'References to studies excluded from this review' in example['references']:
                excludeds_key = 'References to studies excluded from this review'
            elif 'References to excluded reviews' in example['references']:
                excludeds_key = 'References to excluded reviews'

            if excludeds_key is not None:
                for reference in example['references'][excludeds_key]:

                    for study in reference['studies']:

                        # only do N samples per review ########
                        if only_N and n_current_review_samples >= args.N:
                            break
                        #######################################

                        if 'abstract' in study:
                            abstract = dict_to_string(study['abstract'], abstract_section_filter).replace(':', '')
                            if 'This CENTRAL record does not have an abstract.' in abstract:
                                continue

                            abstract = clean_up(abstract, "abstract")

                            # for when the abstract is multilingual
                            if len(abstract.split(' Abstract ')) > 1:
                                abstract = abstract.split(' Abstract ')[1]

                            if 'objectives' not in example["abstract"] or 'selection criteria' not in example["abstract"]:
                                continue

                            objectives = clean_up(example["abstract"]["objectives"], "objectives")
                            selection_criteria = clean_up(example["abstract"]["selection criteria"],
                                                          "selection criteria")
                            new_inputs = [abstract, objectives, selection_criteria]

                            ## ADD REASONING TASK EXAMPLES
                            if reason_next and n_reasons < max_reasons and reasons_count < max_reasons_per_study and 'Exclusion Reason' in reference:
                                new_input = get_tokens_splits(args, new_inputs, prompt_template, prompt_template_len,
                                                              splitter_id, tokenizer, alpaca_format_len+explanation_instruction_template_len)

                                if new_input is not None:
                                    data.append({
                                        'instruction': reason_instruction,
                                        'input': post_clean_up(tokenizer.decode(new_input).replace('<s> ', '').strip()),
                                        'output': reference['Exclusion Reason'].strip(),
                                        'topic': example['meta']['topic'],
                                        'ref_title': study['meta']['title'],
                                        'doi': example['id'],
                                    })
                                    n_reasons += 1
                                    reasons_count += 1
                                    reason_next = args.always_reason
                            else:
                                new_input = get_tokens_splits(args, new_inputs, prompt_template, prompt_template_len,
                                                              splitter_id, tokenizer, alpaca_format_len+instruction_template_len)

                                if new_input is not None:
                                    data.append({
                                        'instruction': instruction_template_str,
                                        'input': post_clean_up(tokenizer.decode(new_input).replace('<s> ', '').strip()),
                                        'output': "Excluded",
                                        'topic': example['meta']['topic'],
                                        'ref_title': study['meta']['title'],
                                        'doi': example['id'],
                                    })
                                    n_current_review_samples += 1
                                    reason_next = True

    return data


def clean_up(to_clean, clean_type):
    to_clean = to_clean.replace(':', '')

    if clean_type == "abstract":
        to_clean = str(re.sub(r'^\s*[Aa]bstract', r'', to_clean)).strip()
    elif clean_type == "selection criteria":
        to_clean = str(re.sub(r'^\s*[Ss]election [Cc]riteria', r'', to_clean)).strip()
    elif clean_type == "objectives":
        to_clean = str(re.sub(r'^\s*[Oo]bjectives', r'', to_clean)).strip()
    return to_clean


def post_clean_up(to_clean):
    # Remove double spaces
    to_clean = re.sub(r'[^\S\r\n]+', ' ', to_clean)

    # Fix duplicate punctuation
    to_clean = re.sub(r'(?P<punct>([^\w\s.-—])\2+)', r'\g<punct>', to_clean)
    to_clean = re.sub(r'(?P<dashes>--)-*', r'\g<dashes>', to_clean)
    to_clean = re.sub(r'(?P<ellipse>\.\.\.)\.*', r'\g<ellipse>', to_clean)

    # Fix spacing issues before punctuation
    to_clean = re.sub(r'(?P<word>\w+)\s*(?P<punct>[\.|\,|\?|;|:|!|%|\p{Sc}])', r'\g<word>\g<punct>', to_clean)

    # Fix spacing issues after punctuation
    to_clean = re.sub(r'(?P<punct>[\.|\,|\?|;|:|!|%])[^\S\r\n]*(?P<word>[a-zA-Z_]+)', r'\g<punct> \g<word>', to_clean)

    # Fix spacing issues with abbreviations
    to_clean = re.sub(r'(?<=[A-Z]\.)\s*[ &]\s*(?=[A-Z]\.)', '', to_clean)

    # Fix bracket spacing errors
    to_clean = re.sub(r'(?P<open>(\(|\{|\[))\s*', r'\g<open>', to_clean)
    to_clean = re.sub(r'\s*(?P<close>(\)|\}|\]))', r'\g<close>', to_clean)
    return to_clean


def get_tokens_splits(args, new_inputs, prompt_template, prompt_template_len, splitter_id, tokenizer, instruction_template_len):
    if len(new_inputs) == 1:
        extra = 0
    else:
        extra = 1

    new_input = '<|insert123|>'.join(new_inputs)
    new_input = tokenizer.encode(new_input, max_length=args.max_input_length - prompt_template_len - instruction_template_len - 2,
                                 padding=False, truncation=True, add_special_tokens=False)

    # if the split indices are cut off then truncate each input section equally until they all fit
    split_indices = [i for i, x in enumerate(new_input) if x == splitter_id]
    split_indices.insert(0, 0)
    split_indices.append(len(new_input) - 1)

    while len(split_indices) != len(prompt_template) + extra and len(new_input) > args.max_input_length:
        new_new_inputs = []

        biggest_input_len = len(max(new_inputs, key=len))

        # try to truncate on sentences but if not just naively truncate
        for new in new_inputs:
            try:
                last_sentence_end = list_rindex(new, '.')
                if 7 * len(new) / 8 < last_sentence_end < len(new) - 1 and len(new) > 2 * biggest_input_len / 3:
                    new_new_inputs.append(new[:last_sentence_end + 1])
                elif len(new) > 2 * biggest_input_len / 3:
                    new_new_inputs.append(new[:7 * len(new) // 8])
                else:
                    new_new_inputs.append(new)
            except ValueError:
                if len(new) > 2 * biggest_input_len / 3:
                    new_new_inputs.append(new[:7 * len(new) // 8])
                else:
                    new_new_inputs.append(new)

        new_inputs = new_new_inputs

        new_input = '<|insert123|>'.join(new_inputs)
        new_input = tokenizer.encode(new_input, max_length=args.max_input_length - prompt_template_len - instruction_template_len - 2,
                                     padding=False, truncation=True, add_special_tokens=False)

        # if the split indices are cut off then truncate each input section equally until they all fit
        split_indices = [i for i, x in enumerate(new_input) if x == splitter_id]
        split_indices.insert(0, 0)
        split_indices.append(len(new_input) - 1)


    for i, prompt_part in enumerate(prompt_template):
        try:
            new_input = new_input[:split_indices[i]] + prompt_part[1:] + \
                                     new_input[split_indices[i]:]
            if i < len(split_indices) - 1:
                split_indices[i + 1:] = [a + len(prompt_part[1:]) for a in split_indices[i + 1:]]
        except IndexError:
            return None
    new_input = [x for x in new_input if x != splitter_id]

    ## now remove repeated substrings of a certain length
    #new_input = remove_repeating_substrings(new_input, 5)

    return new_input


def clean_keys(example):
    for key in list(example.keys()):
        new_key = key.replace(u'\xa0', u' ')
        tmp = example.pop(key)
        example[new_key] = tmp
        if type(example[new_key]) == dict:
            clean_keys(example[new_key])


def multitask_instruct(args, examples, tokenizer):
    alpaca_format_len = len(tokenizer('Below is an instruction that describes a task, paired with an input that provides further context. '
                                  'Write a response that appropriately completes the request.\n\n'
                                  '### Instruction:')['input_ids'])

    splitter_id = tokenizer('<|insert123|>')['input_ids'][-1]

    pico_instructions = args.instruction_template[0]
    pico_prompts = args.prompt_template[0]
    pico_targets = args.target_template[0]

    inc_exc_instruction = args.instruction_template[1]
    inc_exc_prompts = args.prompt_template[1]
    inc_exc_targets = args.target_template[1]

    inc_exc_data = include_exclude(args, examples, tokenizer, splitter_id, inc_exc_instruction, inc_exc_prompts,
                                   inc_exc_targets, alpaca_format_len)

    if not args.inc_exc_only:
        pico_data = pico_separate_look_multiple(args, examples, tokenizer, splitter_id, pico_instructions, pico_prompts,
                                             pico_targets, alpaca_format_len)

        dataset = pico_data + inc_exc_data
    else:
        dataset = inc_exc_data

    return dataset


def list_rindex(li, x):
    for i in reversed(range(len(li))):
        if li[i] == x:
            return i
    raise ValueError("{} is not in list".format(x))


def dict_to_string(dictionary, key_filter=None):
    if key_filter is None:
        key_filter = []
    if dictionary is None:
        return ""
    elif type(dictionary) is str:
        return dictionary
    else:
        if key_filter:
            return " ".join([str(key) + ' are ' + str(value) for key, value in dictionary.items() if not
            any([section in key.lower() for section in key_filter]) or key != 'null'])
        else:
            for key in list(dictionary.keys()):
                if key == 'null':
                    dictionary.pop(key)
                elif type(dictionary[key]) is dict:
                    dictionary[key] = dict_to_string(dictionary[key])
            return " ".join([str(key) + ' ' + str(value.strip()) for key, value in dictionary.items()])


def load_json(file_name):
    with open('./' + file_name + '.json', "r") as file:
        data = json.load(file)
    return data


if __name__ == "__main__":
    from transformers import LlamaTokenizerFast

    args = Namespace(**{
        'max_input_length': 2048,
        'max_output_length': 512,
        'instruction_template': [["Given the abstract, what is the study's Population?", "Given the abstract, what is the study's Intervention?",
                                    "Given the abstract, what is the study's Outcome?", "Given the abstract, what is the study's Outcome?"],
                                 "Given the abstract, objectives and selection criteria should the study be included or excluded?"],
        'prompt_template': ["Abstract: {}",
                       "Abstract: {}\n Objectives: {}\n Selection Criteria: {}\n"],
        'target_template' : [["Population: {}", "Intervention: {}", "Outcome: {}"],
                       ["Included", "Excluded because {}"]],
        'relevant_data_only': False,
        'N': -1,
        'ensure_no_pio_repeat': True,
        'gold': False,
        'inc_exc_only': False,
        'always_reason': False,
        'doi': None
    })

    tokenizer = LlamaTokenizerFast.from_pretrained('elinas/llama-7b-hf-transformers-4.29')
    tokenizer.add_special_tokens({'additional_special_tokens': ['<|insert123|>']})

    cochrane = load_json('./data/eval_cochrane_data')
    formatted = multitask_instruct(args, cochrane, tokenizer)


    # filter out duplicate entries
    formatted = [dict(t) for t in {tuple(d.items()) for d in formatted}]

    print(formatted[0])
    # save formatted data
    with open('data/eval_final_no_exclusion_reasons_w_everything.json', 'w') as f:
        json.dump(formatted, f, indent=4)
