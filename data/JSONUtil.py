import json
from os.path import exists


def store_objects_list_as_json(file_name, objects):
    with open('./data/' + file_name + '.json', 'w+') as outfile:
        json.dump([object.toJSON() for object in objects], outfile, indent=4)


def store_object_as_new_json(file_name, object_instance):
    with open('./data/' + file_name + '.json', 'w+') as outfile:
        json.dump([object_instance.toJSON()], outfile, indent=4)


def store_json(file_name, json_dict):
    with open('./data/' + file_name + '.json', 'w+') as outfile:
        json.dump(json_dict, outfile, indent=4)


def load_json(file_name):
    with open('./data/' + file_name + '.json', "r") as file:
        data = json.load(file)
    return data


def does_json_file_exist(file_title):
    return exists("./data/" + file_title + ".json")


def create_json_or_append_object(file_title, new_object):
    if exists("./data/" + file_title + ".json"):
        with open('./data/' + file_title + '.json', "r+") as file:
            data = json.load(file)
            data.append(new_object.toJSON())
            file.seek(0)
            json.dump(data, file, indent=4)
    else:
        store_object_as_new_json(file_title, new_object)


def save_titles(file_title, title_list):
    if exists("./data/" + file_title + ".json"):
        with open('./data/' + file_title + '_titlesonly.json', "r+") as file:
            data = json.load(file)
            data.extend(title_list)
            file.seek(0)
            json.dump(data, file, indent=4)
    else:
        with open('./data/' + file_title + '_titlesonly.json', 'w+') as outfile:
            json.dump(title_list, outfile, indent=4)


def get_fail_data(topic_title):
    file_title = topic_title_to_file_title(topic_title)
    if exists("./data/fail_data_" + file_title + ".json"):
        print("Loading topic's fail data...")
        fail_data = load_json("fail_data_" + file_title)
    else:
        print("Creating new fail data for topic...")
        fail_data = {
            "incomplete": {},
            "next scrape": 0,
            "file title": topic_title_to_file_title(topic_title),
            "reference host domains": {},
            "finished": 0,
            "success": 0,
            "fail": 0,
            "failures": {},
            "completed": []
        }
    return fail_data


def topic_title_to_file_title(topic_title):
    return topic_title.replace(" ", "_").lower()
