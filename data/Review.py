class Review:
    def __init__(self, doi, authors, publish_date, title, abstract, data):
        self.doi = doi

        # is this a list of authors?
        self.authors = authors

        self.publish_date = publish_date
        self.title = title
        self.abstract = abstract

        self.data = data

        self.references = {}

    def add_reference_group(self, reference_type, references):
        self.references[reference_type] = references

    def toJSON(self):
        if self.references:
            return {
                'id': self.doi,
                'meta': {
                    'authors': self.authors,
                    'publish_date': self.publish_date,
                    'title': self.title
                },
                'abstract': self.abstract,
                'data': self.data,
                'references': self.references
            }
        else:
            return {
                'id': self.doi,
                'meta': {
                    'authors': self.authors,
                    'publish_date': self.publish_date,
                    'title': self.title
                },
                'abstract': self.abstract,
                'data': self.data
            }

    def add_to_existing(self, rev_dict):
        rev_dict['id'] = self.doi
        if 'meta' in rev_dict:
            if self.authors:
                rev_dict['meta']['authors'] = self.authors
            if self.publish_date:
                rev_dict['meta']['publish_date'] = self.publish_date
            if self.title:
                rev_dict['meta']['title'] = self.title
        else:
            rev_dict['meta'] = {
                'authors': self.authors,
                'publish_date': self.publish_date,
                'title': self.title
            }
        rev_dict['abstract'] = self.abstract
        rev_dict['data'] = self.data
        if self.references:
            rev_dict['references'] = self.references

    def __bool__(self):
        if self.authors and self.title and self.abstract:
            return True
        else:
            return False