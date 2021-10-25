from __future__ import annotations
from .optimizer import DPOptimizer

from typing import Callable, List, Optional

import torch
from torch import nn
from torch.optim import Optimizer



class DistributedDPOptimizer(DPOptimizer):
    def __init__(
        self,
        optimizer: Optimizer,
        *,
        noise_multiplier: float,
        max_grad_norm: float,
        expected_batch_size: Optional[int],
        loss_reduction: str = "mean",
    ):
        super().__init__(optimizer, noise_multiplier=noise_multiplier, max_grad_norm=max_grad_norm, expected_batch_size=expected_batch_size, loss_reduction=loss_reduction)
        self.rank = torch.distributed.get_rank()
        self.world_size = torch.distributed.get_world_size()


    def add_noise(self):
        # Noise only gets added to the first worker
        if self.rank == 0:
            super().add_noise()
        else:
            for p in self.params:
                p.grad = p.summed_grad


    def reduce_gradients(self):
        for p in self.params:
            if not p.requires_grad:
                continue
            torch.distributed.all_reduce(p.grad, op=torch.distributed.ReduceOp.SUM)
            if self.loss_reduction == "mean":
                p.grad /= self.world_size

    def step(self, closure: Optional[Callable[[], float]] = None) -> Optional[float]:
        self.pre_step()
        self.reduce_gradients()

        return self.optimizer.step(closure)