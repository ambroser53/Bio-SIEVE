from transformers import Seq2SeqTrainer

class PEFTFriendlySeq2SeqTrainer(Seq2SeqTrainer):
    def _load_from_checkpoint(self, resume_from_checkpoint, model=None):
        pass