# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
from typing import List
from typing import Text
import tempfile

import launch
from launch.utilities import normalize_to_list_of_substitutions, perform_substitutions

class ReplaceString(launch.Substitution):
  def __init__(self,
    source_file: launch.SomeSubstitutionsType,
    replacements: dict):
    super().__init__()

    self.__source_file = normalize_to_list_of_substitutions(source_file)
    self.__replacements = {}
    for key in replacements:
        self.__replacements[key] = normalize_to_list_of_substitutions(replacements[key])

  def perform(self, context: launch.LaunchContext) -> Text:
    extracted_replacements = {}
    for key in self.__replacements:
      extracted_replacements[key] = perform_substitutions(context, self.__replacements[key])
    
    try:
      input_file = open(perform_substitutions(context, self.__source_file), 'r')
      output_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
      for line in input_file:
        for key, value in extracted_replacements.items():
            if key in line:
              line = line.replace(key, value)
        output_file.write(line)
    except Exception as err:
      print('ReplaceString substitution error: ', err)
    finally:
      input_file.close()
      output_file.close()
    return output_file.name   