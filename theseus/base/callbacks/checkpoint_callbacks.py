import os
import os.path as osp
from typing import Dict

import torch

from theseus.base.callbacks import Callbacks
from theseus.base.utilities.loading import load_state_dict
from theseus.base.utilities.loggers.observer import LoggerObserver

LOGGER = LoggerObserver.getLogger("main")


class TorchCheckpointCallbacks(Callbacks):
    """
    Callbacks for saving checkpoints.
    Features:
        - Load checkpoint at start
        - Save checkpoint every save_interval
        - Save checkpoint if metric value is improving

    save_dir: `str`
        save directory
    save_interval: `int`
        iteration cycle to save checkpoint
    best_key: `str`
        save best based on metric key
    resume: `str`
        path to .pth to resume checkpoints

    """

    def __init__(
        self,
        save_dir: str = "runs",
        save_interval: int = None,
        best_key: str = None,
        resume: str = None,
        **kwargs,
    ) -> None:
        super().__init__()

        self.best_value = 0
        self.best_key = best_key
        self.save_dir = osp.join(save_dir, "checkpoints")
        os.makedirs(self.save_dir, exist_ok=True)
        self.save_interval = save_interval
        self.resume = resume

    def auto_get_save_interval(self, train_fraction=0.5):
        """
        Automatically decide the number of save interval
        """
        trainloader = self.params["trainer"].trainloader
        num_iterations_per_epoch = len(trainloader)
        save_interval = int(train_fraction * num_iterations_per_epoch)
        return save_interval

    def load_checkpoint(self, path, trainer):
        """
        Load all information the current iteration from checkpoint
        """
        LOGGER.text("Loading checkpoints...", level=LoggerObserver.INFO)
        state_dict = torch.load(path, map_location="cpu")
        trainer.iters = load_state_dict(trainer.iters, state_dict, "iters")
        if trainer.scaler:
            trainer.scaler = load_state_dict(
                trainer.scaler, state_dict, trainer.scaler.state_dict_key
            )
        self.best_value = load_state_dict(self.best_value, state_dict, "best_value")

    def save_checkpoint(self, trainer, iters, outname="last"):
        """
        Save all information of the current iteration
        """
        weights = {
            "model": trainer.model.model.state_dict(),
            "optimizer": trainer.optimizer.state_dict(),
            "scheduler": trainer.scheduler.state_dict(),
            "iters": iters,
            "best_value": self.best_value,
        }

        if trainer.scheduler:
            weights["scheduler"] = trainer.scheduler.state_dict()

        if trainer.scaler:
            weights[trainer.scaler.state_dict_key] = trainer.scaler.state_dict()

        torch.save(weights, os.path.join(self.save_dir, outname) + ".pth")
        LOGGER.text(
            f"Save checkpoints to {os.path.join(self.save_dir, outname)}" + ".pth",
            level=LoggerObserver.INFO,
        )

    def sanitycheck(self, logs: Dict = None):
        """
        Sanitycheck before starting. Run only when debug=True
        """
        if self.resume is not None:
            self.load_checkpoint(self.resume, self.params["trainer"])
            self.resume = None  # Turn off so that on_start would not be called

    def on_start(self, logs: Dict = None):
        """
        Before going to the main loop
        """
        if self.resume is not None:
            self.load_checkpoint(self.resume, self.params["trainer"])

        if self.save_interval is None:
            self.save_interval = self.auto_get_save_interval()
            LOGGER.text(
                "Save interval not specified. Auto calculating...",
                level=LoggerObserver.DEBUG,
            )

    def on_finish(self, logs: Dict = None):
        """
        After finish training
        """

        iters = logs["iters"]
        num_iterations = logs["num_iterations"]

        self.save_checkpoint(self.params["trainer"], iters=iters)
        LOGGER.text(
            f"Save model at [{iters}|{num_iterations}] to last.pth",
            LoggerObserver.INFO,
        )

    def on_train_batch_end(self, logs: Dict = None):
        """
        On training batch (iteration) end
        """

        iters = logs["iters"]
        num_iterations = logs["num_iterations"]

        # Saving checkpoint
        if iters % self.save_interval == 0 or iters == num_iterations - 1:
            self.save_checkpoint(self.params["trainer"], iters=iters)
            LOGGER.text(
                f"Save model at [{iters}|{num_iterations}] to last.pth",
                LoggerObserver.INFO,
            )

    def on_val_epoch_end(self, logs: Dict = None):
        """
        On validation batch (iteration) end
        """

        iters = logs["iters"]
        num_iterations = logs["num_iterations"]
        metric_dict = logs["metric_dict"]

        if self.best_key is None:
            return

        if not self.best_key in metric_dict.keys():
            LOGGER.text(
                f"{self.best_key} key does not present in metric. Available keys are: {metric_dict.keys()}",
                LoggerObserver.WARN,
            )
            return

        # Saving checkpoint
        if metric_dict[self.best_key] > self.best_value:
            if (
                iters > 0
            ):  # Have been training, else in evaluation-only mode or just sanity check
                LOGGER.text(
                    f"Evaluation improved from {self.best_value} to {metric_dict[self.best_key]}",
                    level=LoggerObserver.SUCCESS,
                )
                self.best_value = metric_dict[self.best_key]
                self.save_checkpoint(
                    self.params["trainer"], iters=iters, outname="best"
                )

                LOGGER.text(
                    f"Save model at [{iters}|{num_iterations}] to best.pth",
                    LoggerObserver.INFO,
                )
