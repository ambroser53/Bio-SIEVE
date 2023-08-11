# Dataset

The safety-first dataset is provided directly as it was developed as part of the project.


For samples taken from [Cochrane Reviews](https://www.cochranelibrary.com/about/about-cochrane-reviews), a list of DOIs is provided. Each split of the Instruct Cochrane dataset can be built from the list provided in each of the doi files in this directory:

| Dataset | Description | Filename | Samples |
| --- | --- | --- | ---  |
| Train | Training dataset containing all tasks (inc/exc, PICO, exc. reasoning) | train_dois.txt |  |
| Test | Test set containing inc/exc tasks and exc. reasoning | test_dois.txt |  |
| Subset | A selection of samples for inc/exc from the test set for which reviews had > 100 submitted abstracts present. There are a total of 13 reviews | subset_dois.txt |  |