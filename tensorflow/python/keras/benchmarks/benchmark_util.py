# Copyright 2020 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Common utils for benchmark."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import timeit
import numpy as np

import tensorflow as tf


class TimerCallBack(tf.keras.callbacks.Callback):
  """Callback for logging time in each epoch or batch."""

  def __init__(self):
    self.times = []
    self.timer = timeit.default_timer
    self.startup_time = timeit.default_timer()
    self.recorded_startup = False

  def on_epoch_begin(self, e, logs):
    self.epoch_start_time = self.timer()

  def on_epoch_end(self, e, logs):
    self.times.append(self.timer() - self.epoch_start_time)

  def on_batch_end(self, e, logs):
    if not self.recorded_startup:
      self.startup_time = self.timer() - self.startup_time
      self.recorded_startup = True


def measure_performance(model_fn,
                        x=None,
                        y=None,
                        epoch=2,
                        batch_size=32,
                        run_iters=4,
                        optimizer=None,
                        loss=None,
                        metrics=None,
                        verbose=0,
                        num_gpus=0,
                        distribution_strategy='off'):
  """Run models and measure the performance.

  Arguments:
    model_fn: Model function to be benchmarked.
    x: Input data. See `x` in the `fit()` method of `keras.Model`.
    y: Target data. See `y` in the `fit()` method of `keras.Model`.
    epoch: Integer. Number of epochs to train the model. If unspecified, `epoch`
      will default to 2.
    batch_size: Integer. Number of samples per gradient update. If unspecified,
      `batch_size` will default to 32.
    run_iters: Integer. Number of iterations to run the performance measurement.
      If unspecified, `run_iters` will default to 4.
    metrics: Lists of metrics to be evaluated by the model during training. See
      `metrics` in the `compile()` method of  `keras.Model`.
    verbose: 0, 1, 2. Verbosity mode. See `verbose` in the `fit()` method of
      `keras.Model`. If unspecified, `verbose` will default to 0.
    num_gpus: Number of GPUs to run the model.
    distribution_strategy: Distribution strategies. It could be
      `multi_worker_mirrored`, `one_device`, `mirrored`. If unspecified,
      `distribution_strategy` will default to 'off'.
        TODO: `TPU`, `parameter_server`.

  Returns:
    Performance summary, which contains build_time, compile_time,
    startup_time, avg_epoch_time, wall_time, exp_per_sec, distribution_strategy,
    epoch.

  Raise:
    ValueError: If `x` is none or if `optimizer` is not provided or
    if `loss` is not provided or if `num_gpus` is negative.
  """
  if 'x' is None:
    raise ValueError('Input data is required.')
  if 'optimizer' is None:
    raise ValueError('Optimizer is required.')
  if 'loss' is None:
    raise ValueError('Loss function is required.')
  if num_gpus < 0:
    raise ValueError('`num_gpus` cannot be negative')

  # TODO: (xingyulong@) We will add tfds support later and
  #  get the `num_examples` from info.
  num_examples = x.shape[0]

  build_time_list, compile_time_list, startup_time_list = [], [], []
  avg_epoch_time_list, wall_time_list, exp_per_sec_list = [], [], []
  total_num_examples = epoch * num_examples

  for _ in range(run_iters):
    timer = timeit.default_timer
    t0 = timer()
    model = model_fn()
    build_time = timer() - t0

    t1 = timer()
    model.compile(
        optimizer=optimizer,
        loss=loss,
        metrics=metrics,
    )
    compile_time = timer() - t1
    # Run one warm up epoch.
    model.fit(x=x, y=y, batch_size=batch_size, epochs=1)
    cbk = TimerCallBack()
    t2 = timer()
    model.fit(
        x=x,
        y=y,
        batch_size=batch_size,
        epochs=epoch,
        callbacks=[cbk],
        verbose=verbose)
    end_time = timer()

    build_time_list.append(build_time)
    compile_time_list.append(compile_time)
    startup_time_list.append(cbk.startup_time)
    avg_epoch_time_list.append(np.mean(cbk.times))
    wall_time_list.append(end_time - t0)
    exp_per_sec_list.append(total_num_examples / (end_time - t2))

  results = {
      'build_time': np.mean(build_time_list),
      'compile_time': np.mean(compile_time_list),
      'startup_time': np.mean(startup_time_list),
      'avg_epoch_time': np.mean(avg_epoch_time_list),
      'wall_time': np.mean(wall_time_list),
      'exp_per_sec': np.mean(exp_per_sec_list),
      'distribution_strategy': distribution_strategy,
      'epoch': epoch
  }

  return results
