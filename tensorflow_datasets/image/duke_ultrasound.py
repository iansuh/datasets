"""DAS beamformed phantom images and paired clinical post-processed images."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import csv
import os
import numpy as np
import tensorflow_datasets.public_api as tfds
import tensorflow as tf


_CITATION = """\
@article{DBLP:journals/corr/abs-1908-05782,
  author    = {Ouwen Huang and
               Will Long and
               Nick Bottenus and
               Gregg E. Trahey and
               Sina Farsiu and
               Mark L. Palmeri},
  title     = {MimickNet, Matching Clinical Post-Processing Under Realistic Black-Box
               Constraints},
  journal   = {CoRR},
  volume    = {abs/1908.05782},
  year      = {2019},
  url       = {http://arxiv.org/abs/1908.05782},
  archivePrefix = {arXiv},
  eprint    = {1908.05782},
  timestamp = {Mon, 19 Aug 2019 13:21:03 +0200},
  biburl    = {https://dblp.org/rec/bib/journals/corr/abs-1908-05782},
  bibsource = {dblp computer science bibliography, https://dblp.org}
}"""

_DESCRIPTION = """\
DukeUltrasound is an ultrasound dataset collected at Duke University with a 
Verasonics c52v probe. It contains delay-and-sum (DAS) beamformed data 
as well as data post-processed with Siemens Dynamic TCE for speckle 
reduction, contrast enhancement and improvement in conspicuity of 
anatomical structures. These data were collected with support from the
National Institute of Biomedical Imaging and Bioengineering under Grant 
R01-EB026574 and National Institutes of Health under Grant 5T32GM007171-44."""

_URLS = ['https://arxiv.org/abs/1908.05782', 'https://github.com/ouwen/mimicknet']

_DATA_URL = {
    'phantom_data': 'https://research.repository.duke.edu/downloads/vt150j912',
    'mark_data': 'https://research.repository.duke.edu/downloads/4x51hj56d'
}

_DEFAULT_SPLITS = {
    tfds.Split.TRAIN: 'https://research.repository.duke.edu/downloads/tt44pn391',
    tfds.Split.TEST: 'https://research.repository.duke.edu/downloads/zg64tm441',
    tfds.Split.VALIDATION: 'https://research.repository.duke.edu/downloads/dj52w535x',
    'MARK': 'https://research.repository.duke.edu/downloads/wd375w77v',
    'A': 'https://research.repository.duke.edu/downloads/nc580n18d',
    'B': 'https://research.repository.duke.edu/downloads/7h149q56p'
}


class DukeUltrasound(tfds.core.GeneratorBasedBuilder):
  """DAS beamformed phantom images and paired post-processed images."""

  VERSION = tfds.core.Version("3.0.0")

  def __init__(self, *args, custom_csv_splits={}, **kwargs):
    """custom_csv_splits is a dictionary of { 'name': 'csvpaths'}"""
    super().__init__(*args, **kwargs)
    self.custom_csv_splits = custom_csv_splits

  def _info(self):
    return tfds.core.DatasetInfo(
        builder=self,
        description=_DESCRIPTION,
        features=tfds.features.FeaturesDict({
            'das': {
              'dB': tfds.features.Tensor(shape=(None,), dtype=tf.float32),
              'real': tfds.features.Tensor(shape=(None,), dtype=tf.float32),
              'imag': tfds.features.Tensor(shape=(None,), dtype=tf.float32)
            },
            'dtce': tfds.features.Tensor(shape=(None,), dtype=tf.float32),
            'f0_hz': tfds.features.Tensor(shape=(), dtype=tf.float32),
            'voltage': tfds.features.Tensor(shape=(), dtype=tf.float32),
            'focus_cm': tfds.features.Tensor(shape=(), dtype=tf.float32),
            'height': tfds.features.Tensor(shape=(), dtype=tf.uint32),
            'width': tfds.features.Tensor(shape=(), dtype=tf.uint32),
            'initial_radius': tfds.features.Tensor(shape=(), dtype=tf.float32),
            'final_radius': tfds.features.Tensor(shape=(), dtype=tf.float32),
            'initial_angle': tfds.features.Tensor(shape=(), dtype=tf.float32),
            'final_angle': tfds.features.Tensor(shape=(), dtype=tf.float32),
            'probe': tfds.features.Tensor(shape=(), dtype=tf.string),
            'scanner': tfds.features.Tensor(shape=(), dtype=tf.string),
            'target': tfds.features.Tensor(shape=(), dtype=tf.string),
            'timestamp_id': tfds.features.Tensor(shape=(), dtype=tf.uint32),
            'harmonic': tfds.features.Tensor(shape=(), dtype=tf.bool)
        }),
        supervised_keys=('das/dB', 'dtce'),
        urls=_URLS,
        citation=_CITATION
    )

  def _split_generators(self, dl_manager):
    dl_paths = dl_manager.download_and_extract({**_DEFAULT_SPLITS, **_DATA_URL})
    splits = [
      tfds.core.SplitGenerator(
          name=name,
          num_shards=10,
          gen_kwargs={
              'datapath': {
                  'mark_data': dl_paths['mark_data'],
                  'phantom_data': dl_paths['phantom_data']
              },
              'csvpath': dl_paths[name]
          }) for name, path in _DEFAULT_SPLITS.items()
    ]

    for name, csv_path in self.custom_csv_splits.items():
      splits.append(tfds.core.SplitGenerator(
          name=name,
          num_shards=10,
          gen_kwargs={
              'datapath': dl_paths['data'],
              'csvpath': csv_path
      }))

    return splits

  def _generate_examples(self, datapath, csvpath):
    reader = csv.DictReader(tf.io.gfile.GFile(csvpath))
    for row in reader:
      data_key = 'mark_data' if row['target'] == 'mark' else 'phantom_data'

      filepath = os.path.join(datapath[data_key], row['filename'])
      matfile = tfds.core.lazy_imports.scipy.io.loadmat(tf.io.gfile.GFile(filepath, 'rb'))

      iq = np.abs(np.reshape(matfile['iq'], -1))
      iq = iq/iq.max()
      iq = 20*np.log10(iq)

      yield row['filename'], {
          'das': {
              'dB': iq.astype(np.float32),
              'real': np.reshape(matfile['iq'], -1).real.astype(np.float32),
              'imag': np.reshape(matfile['iq'], -1).imag.astype(np.float32)
          },
          'dtce': np.reshape(matfile['dtce'], -1).astype(np.float32),
          'f0_hz': row['f0'],
          'voltage': row['v'],
          'focus_cm': row['focus_cm'],
          'height': row['axial_samples'],
          'width': row['lateral_samples'],
          'initial_radius': row['initial_radius'],
          'final_radius': row['final_radius'],
          'initial_angle': row['initial_angle'],
          'final_angle': row['final_angle'],
          'probe': row['probe'],
          'scanner': row['scanner'],
          'target': row['target'],
          'timestamp_id': row['timestamp_id'],
          'harmonic': row['harm']
      }
