import random
import re
import time
from typing import List, Union
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup, Tag
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from copy import deepcopy
import ssl

ssl._create_default_https_context = ssl._create_unverified_context


class Element:
    """
     Element is a basic defined scraping unit, which is a tag with a name and attributes. Can be defined recurively
     and scraped at any point in the tree.
    Parameters
    ----------
    name : str
        name of tag
    attribute : str, None
        first attribute of tag
    value: str, None
        value of first attribute of tag to define
    parent: Element, None
        defines parent of this element by which scraping will abide by
    is_multi: bool
        whether to return a list of all tags that match the element or just the first
    retrieve_attribute: str, None
        attribute to retrieve from tag
    """
    def __init__(self, name, attribute=None, value=None, parent=None, is_multi=False, retrieve_attribute=None):
        self.name = name
        if attribute:
            self.attributes = {attribute: value}
        else:
            self.attributes = {}
        # parents are also Element objects
        self.parent = parent

        self.retrieve_attribute = retrieve_attribute

        self.is_multi = is_multi

    def add_attribute(self, attribute, value):
        self.attributes[attribute] = value

    def set_retrieved_attribute(self, new_retrieved_attribute):
        self.retrieve_attribute = new_retrieved_attribute

    def click(self, soup, driver, containing: List[str], with_scroll=False, element_strict=False):
        """
         Clicks the element on the page
         Parameters
        ----------
        soup : BeautifulSoup
            soup to scrape
        driver: webdriver
            driver to use for clicking
        containing: List[str]
            list of strings that the element must contain at least one of
        """
        found_element, _ = get_selenium_element_by_containing(driver, soup, self, containing, element_strict)
        result = click_element_by_containing(driver, found_element, with_scroll)

        if result:
            print("successfully clicked " + str(containing))
        else:
            print("failed to click " + str(containing))

    def remove_child(self, soup, remove_element, upper_limit_element=None):
        scraped_element = self.deepcopy_without_ancestor(upper_limit_element)
        element_tags = get_soup_tags_by_element_object_with_parent(soup, scraped_element)
        removals = []
        for tag in element_tags:
            if remove_element.attributes:
                removals.append(tag.find(remove_element.name, remove_element.attributes).extract().get_text(separator=' '))
            else:
                removals.append(tag.find(remove_element.name).extract().get_text(separator=' '))
        return removals

    def scrape_and_extract(self, soup, upper_limit_element=None):
        scraped_element = self.deepcopy_without_ancestor(upper_limit_element)

        element_tags = get_soup_tags_by_element_object_with_parent(soup, scraped_element)

        if element_tags:
            if self.is_multi:
                return [tag.extract()[self.retrieve_attribute] if self.retrieve_attribute
                        else tag.extract().get_text(separator=' ') for tag in element_tags]
            else:
                tag = element_tags[0]
                return tag.extract()[self.retrieve_attribute] \
                    if self.retrieve_attribute else tag.extract().get_text(separator=' ')
        return None

    def set_parent(self, new_parent):
        self.parent = new_parent
        return self

    def scrape(self, soup, upper_limit_element=None):
        """
         Scrapes the soup for the element and returns the resultant tag or list of tags and their value unless
         attribute retrieval defined
         Parameters
        ----------
        soup : BeautifulSoup
            soup to scrape
        upper_limit_element: Element, None
            element to remove from tree before scraping, this is for when a subset of the original tree is being used
        Returns
        -------
        list of tags or tag
        """
        scraped_element = self.deepcopy_without_ancestor(upper_limit_element)

        element_tags = get_soup_tags_by_element_object_with_parent(soup, scraped_element)

        if element_tags:
            if self.is_multi:
                return [tag[self.retrieve_attribute] if self.retrieve_attribute else tag.get_text(separator=' ')
                        for tag in element_tags]
            else:
                tag = element_tags[0]
                return tag[self.retrieve_attribute] if self.retrieve_attribute else tag.get_text(separator=' ')
        return None

    def scrape_tags(self, soup, upper_limit_element=None):
        scraped_element = self.deepcopy_without_ancestor(upper_limit_element)

        element_tags = get_soup_tags_by_element_object_with_parent(soup, scraped_element)
        if element_tags:
            if self.is_multi:
                return element_tags
            else:
                tag = element_tags[0]
                return tag
        return None

    def get_soup(self, soup, upper_limit_element=None) -> Union[BeautifulSoup, List[BeautifulSoup]]:
        """
         Scrapes the soup for the element and returns the resultant tag or list of tags
         Parameters
        ----------
        soup : BeautifulSoup
            soup to scrape
        upper_limit_element: Element, None
            element to remove from tree before scraping, this is for when a subset of the original tree is being used
        Returns
        -------
        tag : BeautifulSoup, [BeautifulSoup]
            list of tags or tag
        """
        scraped_element = self.deepcopy_without_ancestor(upper_limit_element)

        element_tags = get_soup_tags_by_element_object_with_parent(soup, scraped_element)

        if element_tags:
            if self.is_multi:
                return [tag for tag in element_tags]
            else:
                tag = element_tags[0]
                return tag
        return None

    def deepcopy_without_ancestor(self, ancestor):
        if ancestor is None:
            return self

        deep_copy_parent = None
        if self.parent:
            if ancestor != self.parent:
                deep_copy_parent = self.parent.deepcopy_without_ancestor(ancestor)

        deepcopy = Element(self.name, None, None, deep_copy_parent, self.is_multi, self.retrieve_attribute)
        for attr, val in self.attributes.items():
            deepcopy.add_attribute(attr, val)
        return deepcopy

    def __deepcopy__(self, memodict={}):
        deep_copy = Element(self.name, None, None, self.parent, self.retrieve_attribute, self.is_multi)
        for attr, val in self.attributes.items():
            deep_copy.add_attribute(attr, val)
        return deep_copy

    def is_equal_to(self, tag):
        if tag.name == self.name and all([value.lower() in tag[attribute].lower()
                                          if (attribute in tag.attrs) else False for attribute, value in
                                          self.attributes.items()]):
            if self.parent:
                return self.parent.is_equal_to(tag.parent)
            else:
                return True
        else:
            return False

    def replicate_tags(self, tag):
        for attribute, value in tag.attrs.items():
            self.add_attribute(attribute, value)

    def __str__(self):
        tag_string = "<" + self.name
        for attribute, value in self.attributes.items():
            tag_string += " " + attribute + "=\"" + value + "\""
        tag_string += ">"

        if self.parent:
            tag_string += " with parent " + str(self.parent)
        return tag_string


class ScrapeStructure:
    """
     A class that defines a dictionary style scraping structure that it performs on a soup, splitting via
     a scrape master element and then scraping each element in the scrape format
    Parameters
    ----------------
    scrape_master: Element
        the element that delineates the elements scraped that they must be contained within
    scrape_format: dict
        the structure by which to return each element dictionary found, with each value
        in said dictionary being what defines the element(s) or structure to scrape to put in that field
        can also you ElementDict objects or anything with a scrape method. Can also pass in tuples where the first
        value is a scrape-able object and the second is a function to carry out on whatever is scraped
    Returns
    -------
    list of dictionaries
    """
    def __init__(self, scrape_master, scrape_format):
        # scrape master is the parent element that delineates the elements scraped that they must be contained within
        self.scrape_master = scrape_master

        # the scrape format is the structure by which to return each element dictionary found, with each value
        # in said dictionary being what defines the element(s) or structure to scrape to put in that field
        # can also you ElementDict objects or anything with a scrape method. Can also pass in tuples where the first
        # value is a scrape-able object and the second is a function to carry out on whatever is scraped
        self.scrape_format = scrape_format

    def scrape(self, soup, upper_limit_element=None):
        """

        :param soup: the soup or tags with which to scrape inside of to get the entity sets
        :param upper_limit_element: leave as None if calling from outside the class itself
        :return: an array of dictionaries defining individual scraped elements in the format defined in scrape_format
        """
        output = []

        # due to how the scrape master works, only giving a certain amount of the page's soup for search,
        # Element's above the scrape master itself are removed from scraped Element's hierarchy during the scraping
        # process due to the fact that this ancestry has already been secured and proven beforehand

        # we do this by "deep copying" a class object and then "removing the ancestor" on that copy
        if upper_limit_element:
            temp_scrape_master = self.scrape_master.deepcopy_without_ancestor(upper_limit_element)
        else:
            temp_scrape_master = self.scrape_master

        scrape_groups = get_soup_tags_by_element_object_with_parent(soup, temp_scrape_master)

        # print(str(self) + " found " + str(len(scrape_groups)) + " scraped groups")

        for group_soup in scrape_groups:
            # group_soup = check
            scraped_entity = {}
            for key, scrape_object in self.scrape_format.items():
                # print("key " + key)
                # print("scrape definer: " + str(scrape_object))
                if type(key) is Element:
                    key = key.scrape(group_soup, self.scrape_master)
                    if key is None:
                        continue
                    if type(key) is list:
                        scrape_result = scrape_object.scrape(group_soup, self.scrape_master)
                        if type(scrape_result) is not list:
                            raise ValueError("Key is multi but associated scrape object is not")
                        for k, result in zip(key, scrape_result):
                            scraped_entity[k] = result
                        continue
                if type(scrape_object) is dict:
                    scrape_result = {}
                    for nested_key, nested_scrape_obj in scrape_object.items():
                        nested_scrape_res = nested_scrape_obj.scrape(group_soup, self.scrape_master)
                        if nested_scrape_res:
                            scrape_result[nested_key] = nested_scrape_res
                elif type(scrape_object) is tuple:
                    # tuples passed are in the form (scrape-able, func) where func acts upon what has been scraped
                    func = scrape_object[1]
                    scrape_result = func(scrape_object[0].scrape(group_soup))
                else:
                    scrape_result = scrape_object.scrape(group_soup, self.scrape_master)
                if scrape_result:
                    scraped_entity[key] = scrape_result
                # print("For item " + key + " successfully scraped " + str(scrape_result))
            if scraped_entity:
                output.append(scraped_entity)

        return output

    def __str__(self):
        return "ScrapeStructure mastered by " + str(self.scrape_master) + " and format " + str(self.scrape_format)


class ElementDict:
    def __init__(self, element, key_attribute=None, value_attribute=None, href_missing_base_url=None):
        """
        ElementDict returns a single dictionary where each entry has its key and value set by a single element object
        and pulls separate attributes from elements found.
        :param element: the Element object with which to construct each entry in the ElementDict
        :param key_attribute: the attribute from the scraped Element object to set as the entry keys.
        None for containing text. Must not be equal to value_attribute.
        :param value_attribute: the attribute from the scraped Element object to set as the entry values.
        Set as None for containing text. Must not be equal to key_attribute.
        :param href_missing_base_url: for when scraping the href from an element, this is the base url that is sliced
        in front of any links found without a domain (typically the domain of the site being scraped). Leave as None in
        all other contexts.
        """
        self.element = element
        self.key_attribute = key_attribute
        self.value_attribute = value_attribute
        self.href_missing_base_url = href_missing_base_url

    def scrape(self, soup, upper_limit_element=None):
        self.element.set_retrieved_attribute(self.key_attribute)
        keys = self.element.scrape(soup, upper_limit_element)
        if self.key_attribute == "href" and keys:
            for i, key in enumerate(keys):
                if key[0] == "/":
                    keys[i] = self.href_missing_base_url + key

        self.element.set_retrieved_attribute(self.value_attribute)
        values = self.element.scrape(soup, upper_limit_element)
        if self.value_attribute == "href" and values:
            for i, value in enumerate(values):
                if value[0] == "/":
                    values[i] = self.href_missing_base_url + value

        if keys and values:
            keys = [key.strip() for key in keys]
            return dict(zip(keys, values))
        else:
            return {}

    def __str__(self):
        if self.key_attribute is None:
            key = "text"
        else:
            key = self.key_attribute
        if self.value_attribute is None:
            value = "text"
        else:
            value = self.value_attribute
        return "ElementDict defined by " + str(self.element) + \
               " with key attribute as " + key + " and value attribute as " + value


# Make sure recurse_element, tagger_element, and content_element are all simply a name
# (and maybe some attributes but preferably not) and don't have parents
class RecursiveScrapeTagger:
    def __init__(self, master_element, recurse_element, tagger_elements, content_elements):
        self.master_element = master_element
        self.recurse_element = recurse_element
        self.tagger_elements = tagger_elements
        self.content_elements = content_elements

    def scrape(self, soup):
        try:
            master_tag = get_soup_tags_by_element_object_with_parent(soup, self.master_element)[0]
        except IndexError:
            raise NoSuchElementException("ERROR: Unable to find master tag of RecursiveScrapeTagger - "
                                         + str(self.master_element))
        title, content = self.segmented_scrape(master_tag, self.master_element, soup)
        return content

    def segmented_scrape(self, tag, current_upper, soup):
        tag_title = None
        contented_elements = []
        output = {}
        for inner_tag in tag.contents:
            if self.recurse_element.set_parent(current_upper).is_equal_to(inner_tag):
                recurse = deepcopy(self.recurse_element)
                recurse.replicate_tags(inner_tag)
                title, everything_else = self.segmented_scrape(inner_tag, recurse, soup)
                output[title] = everything_else
            elif any([content.set_parent(current_upper).is_equal_to(inner_tag) for content in self.content_elements]):
                content = deepcopy([content for content in self.content_elements
                                    if content.set_parent(current_upper).is_equal_to(inner_tag)][0])
                content.replicate_tags(inner_tag)
                contented_elements.append(content.scrape(soup))
            elif any([tagger.set_parent(current_upper).is_equal_to(inner_tag) for tagger in self.tagger_elements]):
                tagger_element = deepcopy([tagger for tagger in self.tagger_elements
                                           if tagger.set_parent(current_upper).is_equal_to(inner_tag)][0])
                tagger_element.replicate_tags(inner_tag)
                tag_title = tagger_element.scrape(soup)

        if tag_title is None:
            return None, output

        if contented_elements:
            content_string = ' '.join(contented_elements)
            if output:
                output[tag_title] = content_string
            else:
                output = content_string

        return tag_title, output


class TableScraper:
    def __init__(self, table_element):
        self.table_element = table_element

    def scrape(self, soup: BeautifulSoup, scrape_master=None):
        output = {}
        table = get_soup_tags_by_element_object_with_parent(soup, self.table_element)[0]
        section_dict = {}
        section_title = None
        rows = [c for c in table.contents if type(c) is Tag]
        column_titles = []
        for row in rows:
            columns = row.contents
            columns = [column for column in columns if type(column) is Tag]
            try:
                for i, column in enumerate(columns):
                    if len(columns) == 1:
                        if section_title:
                            output[section_title] = section_dict
                            section_dict = {}
                            column_titles = []
                        section_title = column.text.strip()
                    elif len(columns) == 2:
                        if i == 0:
                            row_title = column.text.strip()
                        else:
                            section_dict[row_title] = column.text.strip()
                    else:
                        if column.find_all("b"):
                            column_titles.append(column.text.strip())
                        else:
                            if column_titles and i == 0:
                                row_title = column.text.strip()
                                section_dict[row_title] = {}
                            elif column_titles:
                                section_dict[row_title][column_titles[i]] = column.text.strip()
                            elif i == 0:
                                row_title = column.text.strip()
                                section_dict[row_title] = ''
                            else:
                                section_dict[row_title] += column.text
            except IndexError:
                pass
            except TypeError:
                pass
            except KeyError:
                pass
        if section_title:
            output[section_title] = section_dict

        if not section_title and not output:
            output = section_dict
        elif not section_title:
            output["other"] = section_dict

        return output


def scrape_header_body_under_master_or_default_to_element(soup, master, part_header, body, element):
    parts = ScrapeStructure(master, {part_header: body}).scrape(soup)
    result = None
    try:
        result = {header.lower(): body for part in parts for header, body in part.items()}
    except:
        pass
    if not result:
        result = element.scrape(soup)

    return result


def scrape_with_extract_as_key(soup, element, element_extract):
    tags = get_soup_tags_by_element_object_with_parent(soup, element)
    result = {}
    for tag in tags:
        # try:
        key = tag.find_all(
            lambda found_tag: found_tag.name == element_extract.name and value.lower() in found_tag[attribute].lower()
            if (attribute in found_tag.attrs) else False for attribute, value in
            element_extract.attributes.items())[0].extract()
        scrape = tag.get_text(separator=' ')
        result[key] = scrape
        # except IndexError:
        #    pass
    return result


def get_href_from_element_by_containing(soup, element, containing):
    element_tags = soup.find_all(lambda tag: tag.name == element.name and ((value.lower() in tag[attribute].lower())
                                                                           if (attribute in tag.attrs) else False for
                                                                           attribute, value in element.attributes) and
                                             containing.lower() in tag.text.lower())
    element_tags = filter_tags_by_parent(soup, element, element_tags)
    try:
        return element_tags[0]['href']
    except KeyError:
        raise NoSuchElementException("ERROR: Found element " + str(element) + " that contained " + containing +
                                     " but it had no href attribute attached")
    except IndexError:
        raise NoSuchElementException("ERROR: Could not find element " + str(element) + " that contained " + containing)


def javascript_click_element(driver, element):
    xpath = "//" + element.name + "[@" + list(element.attributes.keys())[0] + "=\"" + list(element.attributes.values())[
        0] + "\"]"
    s = driver.find_element_by_xpath(xpath)
    # perform click with execute_script method
    driver.execute_script("arguments[0].click();", s)

def click_element_by_containing(driver, found_element, with_scroll=False):
    if found_element:
        if with_scroll:
            driver.execute_script("arguments[0].scrollIntoView();", found_element)
        #found_element.click()
        driver.execute_script("arguments[0].click();", found_element)
        return True

    return False


def get_selenium_element_by_containing(driver, soup, element, containing, element_strict=False):
    if element_strict:
        found_element, found_xpath = find_selenium_element_xpath_by_element(driver, element, containing[0])
    else:
        for useless_element in soup.findAll(['script', 'style']):
            useless_element.extract()

        element_tag = get_tag_by_element_containing(soup, element, containing)

        if not element_tag:
            print("couldn't find any element to press containing: " + str(containing))
            return None, None

        found_element, found_xpath = find_selenium_element_xpath_by_soup_tag(driver, element_tag)

    return found_element, found_xpath


def get_tag_by_element_containing(soup: BeautifulSoup, element: Element, containing: List[str]) -> Tag:
    element_tag = None
    for string in containing:
        element_tag = soup.find(lambda tag: tag.name == element.name and ((value.lower() in tag[attribute].lower())
                                                                          if (attribute in tag.attrs) else False for
                                                                          attribute, value in element.attributes) and
                                            string.lower() in tag.text.lower())
        if element_tag:
            print("found element "+str(element)+ " containing: " + string)
            break
    return element_tag


def click_button_by_containing(driver, soup, containing):
    for element in soup.findAll(['script', 'style']):
        element.extract()
    # cookies_tag = precookie_soup.find_all("button", string=lambda x: x and x.lower()=='allow all')

    button_tag = None

    for string in containing:
        button_tag = soup.find(lambda tag: tag.name == "button" and string.lower() in tag.text.lower())
        if button_tag:
            print("found button to press containing: " + string)
            break

    if not button_tag:
        print("couldn't find any button to press containing: " + str(containing))
        return None

    # when using .find_all

    # for i in range(len(button_tag)):
    #   for attribute, content in button_tag[i].attrs.items():

    found_element, found_xpath = find_selenium_element_xpath_by_soup_tag(driver, button_tag)

    if found_element:
        try:
            WebDriverWait(driver, 20).until(expected_conditions.element_to_be_clickable((By.XPATH, found_xpath)))
            found_element.click()
            time.sleep(1)
            return True
        except:
            print("program timed out waiting for the " + str(containing) + " button to become clickable")
            print("skipping button...")

    return False


def find_selenium_element_xpath_by_element(driver, element: Element, containing=None):
    found_element = None
    found_xpath = None
    for attribute, content in element.attributes.items():
        if attribute == "type":
            continue
        else:
            new_xpath = "//" + element.name + "[@" + attribute + "=\"" + content + "\"]"
            if containing:
                new_xpath += "[text()[contains(., '" + containing + "')]]"

        try:
            found_element = driver.find_element(By.XPATH, new_xpath)
            found_xpath = new_xpath
            print("Found " + element.name + " element with " + attribute + " attribute set to value: " + new_xpath)
            break
        except NoSuchElementException:
            print("Found no " + element.name + " element with " + attribute + " attribute set to value: " + new_xpath)
            print("Trying next attribute")
    return found_element, found_xpath

def find_selenium_element_xpath_by_soup_tag(driver, soup_tag: Tag):
    found_element = None
    found_xpath = None
    for attribute, content in soup_tag.attrs.items():
        if attribute == "type":
            continue
        else:
            new_xpath = "//" + soup_tag.name + "[@" + attribute + "=\"" + content + "\"]"

        try:
            found_element = driver.find_element(By.XPATH, new_xpath)
            found_xpath = new_xpath
            print("Found " + soup_tag.name + " element with " + attribute + " attribute set to value: " + new_xpath)
            break
        except NoSuchElementException:
            print("Found no " + soup_tag.name + " element with " + attribute + " attribute set to value: " + new_xpath)
            print("Trying next attribute")
    return found_element, found_xpath


def find_selenium_element_xpath_by_soup_tag_complete(driver, soup_tag):
    found_element = None
    found_xpath = None
    new_xpath = "//" + soup_tag.name
    i = 0
    if soup_tag.attrs:
        new_xpath += "["
    for attribute, content in soup_tag.attrs.items():
        if attribute == "type":
            continue
        elif i > 0:
            new_xpath += " and "
        new_xpath += "@" + attribute + "=\"" + content + "\""
        i += 1
    if soup_tag.attrs:
        new_xpath += "]"

    try:
        found_element = driver.find_element(By.XPATH, new_xpath)
        found_xpath = new_xpath
        print("Found " + soup_tag.name + " element with " + attribute + " attribute set to value: " + new_xpath)
    except NoSuchElementException:
        print("Found no " + soup_tag.name + " element with " + attribute + " attribute set to value: " + new_xpath)
    return found_element, found_xpath


def get_tags_by_tag_type_containing_text(soup, tag_type, containing_text):
    return soup.find_all(tag_type, string=re.compile(containing_text, re.I))


def get_all_text_by_containing(soup, containing):
    info = {}

    for element in soup.findAll(['script', 'style']):
        element.extract()

    for string in containing:
        matches = soup.find_all(string=re.compile(string, re.I))
        # matches = soup.find_all(lambda tag: string.lower() in tag.text.lower())

        if matches:
            print(str(len(matches)) + " matches containing " + string)

            # get the smallest match's parent (most likely to be a title)
            good_match = False

            while not good_match and len(matches) > 0:
                tag = min(matches, key=tag_compare)
                try:
                    tag_proper = tag.parent

                    pulled_text = list(tag_proper.parent.stripped_strings)[1:]

                    # check that it has not just pulled a header
                    if len(pulled_text) > 0:
                        info[string] = pulled_text
                        good_match = True
                    else:
                        # has pulled just a header, traverse sideways
                        print("trying tag sibling:")

                        tag_sibling = tag_proper.next_sibling
                        print(tag_sibling)

                        # TODO refactor to make nicer

                        if len(list(tag_sibling.stripped_strings)) > 0:
                            info[string] = list(tag_sibling.stripped_strings)
                            good_match = True
                        else:
                            print("trying tag parent sibling")
                            tag_parent = tag_proper.parent
                            tag_parent_sibling = tag_parent.next_sibling
                            if len(list(tag_parent_sibling.stripped_strings)) > 0:
                                info[string] = list(tag_parent_sibling.stripped_strings)
                                good_match = True
                            else:
                                print("trying tag parent parent sibling")
                                tag_parent_parent = tag_parent.parent
                                tag_parent_parent_sibling = tag_parent_parent.next_sibling
                                if len(list(tag_parent_parent_sibling.stripped_strings)) > 0:
                                    info[string] = list(tag_parent_parent_sibling.stripped_strings)
                                    good_match = True
                                else:
                                    print("found tag " + tag + " is unsuitable (header only with no suitable siblings)")
                                    matches.remove(tag)

                except:
                    print("found tag " + tag + " is unsuitable (too high in DOM)")
                    matches.remove(tag)

    return info


def get_soup_tags_by_attribute_value(soup, element_type, attribute, value):
    return soup.find_all(
        lambda tag: tag.name == element_type and (value.lower() in tag[attribute].lower())
        if (attribute in tag.attrs) else False)


def get_soup_tags_by_element_object(soup, element):
    return soup.find_all(
        lambda tag: tag.name == element.name and value.lower() in tag[attribute].lower()
        if (attribute in tag.attrs) else False for attribute, value in
        element.attributes.items())


def get_soup_tags_by_element_object_with_parent(soup, element):
    if element.attributes:
        matching_tags = soup.find_all(
            lambda tag: tag.name == element.name and value.lower() in tag[attribute].lower()
            if (attribute in tag.attrs) else False for attribute, value in
            element.attributes.items())
    else:
        matching_tags = soup.find_all(lambda tag: tag.name == element.name)

    if matching_tags:
        matching_tags = filter_tags_by_parent(soup, element, matching_tags)
    return matching_tags


def filter_tags_by_parent(soup, element, matching_tags):
    if element.parent is not None:
        potential_parent_tags = get_soup_tags_by_element_object_with_parent(soup, element.parent)
        matching_tags = [matching_tag for matching_tag in matching_tags
                         if matching_tag.parent in potential_parent_tags]
    return matching_tags


def get_text_by_element_object_grouped_by_parent(soup, element):
    """
    Make sure to pass in an Element object that has a parent, this is for getting all elements of description element
    that are under a parent of description similar to the parent Element object attached to the passed element

    :param soup: beautifulSoup object
    :param element: the Element object to collect the text of all of them with set parent
    :return: array of strings for each group of elements under a single parent
    """
    text_groups_by_parent = []

    potential_parent_tags = get_soup_tags_by_element_object_with_parent(soup, element.parent)

    # for every potential parent, get all children that match the element and concatenate them into the same string
    for parent in potential_parent_tags:
        child_tags = parent.find_all(
            lambda tag: tag.name == element.name and value.lower() in tag[attribute].lower()
            if (attribute in tag.attrs) else False for attribute, value in
            element.attributes.items())
        child_text = ' '.join([child.get_text(separator=' ') for child in child_tags])
        text_groups_by_parent.append(child_text)

    return text_groups_by_parent


def format_soup(soup):
    for element in soup.findAll(['script', 'style']):
        element.extract()
    return soup


def get_text_by_element(soup, element_type, attribute, value):
    for element in soup.findAll(['script', 'style']):
        element.extract()

    text_tags = get_soup_tags_by_attribute_value(soup, element_type, attribute, value)

    for element in text_tags:
        if element.stripped_strings:
            print("Found " + element_type + " element with " + attribute + " attribute set to value: " + value)
            return element.stripped_strings

    print(
        "Found no text inside any " + element_type + " element with " + attribute + " attribute set to value: " + value)
    return None


def tag_compare(tag):
    print(str(list(tag.strings)))
    return len(str(list(tag.strings)))


def check_if_phrases_in_page(soup, phrases):
    for phrase in phrases:
        matches = soup.find_all(lambda tag: phrase.lower() in tag.text.lower())
        # print(matches)
        if matches:
            return True

    return False


def wait_for_page_to_load_element_type(driver, element_type):
    try:
        WebDriverWait(driver, 10).until(
            expected_conditions.presence_of_all_elements_located((By.TAG_NAME, element_type)))
        return True
    except:
        print("Could find no " + element_type + " in the page to wait for")
        return False


def wait_for_page_to_load_element_types(driver, element_types):
    for element in element_types:
        try:
            WebDriverWait(driver, 10).until(
                expected_conditions.presence_of_all_elements_located((By.TAG_NAME, element)))
            return True
        except:
            print("Could find no " + element + "in the page to wait for")
    return False


def wait_for_page_to_load_element(driver, element_type, attribute, content):
    css_selector = element_type + "[" + attribute + "='" + content + "']"

    try:
        if driver.find_elements((By.CSS_SELECTOR, css_selector)).size() != 0:
            print("found the " + element_type + " element")
        else:
            print("couldn't even find the " + element_type + " element")
        WebDriverWait(driver, 5).until(
            expected_conditions.presence_of_all_elements_located((By.CSS_SELECTOR, css_selector)))
        return True
    except:
        print("Could find no " + element_type + " with attribute " + attribute + ": " + content +
              " in the page to wait for (searched with CSS selector)")


def scrape_page(driver, url, middle_func=None, middle_func_args=None):
    if middle_func_args is None:
        middle_func_args = [None]
    driver.get(url)
    if middle_func is not None:
        time.sleep(3)
        middle_func(driver, BeautifulSoup(driver.page_source, 'html.parser', multi_valued_attributes=None), *middle_func_args)

    time.sleep(1)
    return BeautifulSoup(driver.page_source, 'html.parser', multi_valued_attributes=None)


def rescrape_page_after_clicks(driver, soup, element, containing):
    # click_element_by_containing(driver, soup, element, containing)
    javascript_click_element(driver, element)
    time.sleep(1)
    return BeautifulSoup(driver.page_source, 'html.parser', multi_valued_attributes=None)


def rescrape_but_wait_random(driver):
    wait_time = random.uniform(3, 10)
    time.sleep(wait_time)
    return BeautifulSoup(driver.page_source, 'html.parser', multi_valued_attributes=None)


def scrape_page_but_wait(driver, url, elements):
    driver.get(url)
    for element in elements:
        if element.attributes:
            wait_for_page_to_load_element(driver, element.name, list(element.attributes.keys())[0],
                                          list(element.attributes.values())[0])
        else:
            wait_for_page_to_load_element_type(driver, element.name)
    return BeautifulSoup(driver.page_source, 'html.parser', multi_valued_attributes=None)


def get_real_url(driver, url):
    driver.get(url)
    time.sleep(2)
    return driver.current_url


def scrape_page_with_real_url(driver, url):
    driver.get(url)
    time.sleep(2)
    return BeautifulSoup(driver.page_source, 'html.parser', multi_valued_attributes=None), driver.current_url

