/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2022 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef __LOCAL_MEDIA_INPUT_NODE_H_
#define __LOCAL_MEDIA_INPUT_NODE_H_

#include "nodes/base/baseMediaInputNode.hpp"

namespace hce {

namespace ai {

namespace inference {

class MediaReader {
  public:

    MediaReader();
    
    ~MediaReader();
    readMediaStatus_t readBufferFromFile(std::string& mediaStr);

    bool init(const std::string& fileName, const std::string& type, const int readBufferSize);
    void reset();

  private:
    std::string m_fileName;
    std::string m_type;       // media type: video, image
    std::fstream m_fs;
    size_t m_length;          // length of file
    size_t m_readLength;      // successfully read length
    int m_bufferSize;
};


class LocalMediaInputNode : public baseMediaInputNode {
 public:
  LocalMediaInputNode(std::size_t totalThreadNum);

  virtual ~LocalMediaInputNode(){};

  /**
  * @brief Parse params, called by hva framework right after node instantiate.
  * @param config Configure string required by this node.
  */
  virtual hva::hvaStatus_t configureByString(
      const std::string& config) override;

  /**
  * @brief Constructs and returns a node worker instance: LocalMediaInputNodeWorker.
  * @param void
  */
  std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker() const override;

 private:
  hva::hvaConfigStringParser_t m_configParser;
  std::string m_mediaType;
  std::string m_dataSource;
  int m_readBufferSize;
};

class LocalMediaInputNodeWorker : public baseMediaInputNodeWorker {
 public:
  LocalMediaInputNodeWorker(hva::hvaNode_t* parentNode,
                            const std::string& mediaType,
                            const std::string& dataSource,
                            const int readBufferSize);

  void init() override;

  virtual const std::string nodeClassName() const override {
    return "LocalMediaInputNode";
  };

 private:
 
  /**
  * @brief read media buffer from local file, local file can be image or video, specified by m_mediaType
  * @param fileName local file path
  * @param mediaStr media buffer
  */
  bool readMediaToBuf(const std::string& fileName, std::string& mediaStr);
  
  /**
  * @brief to process media content from blob
  * @param buf buffer from blob, should be local path
  * @param content acquired media content
  * @param meta HceDatabaseMeta, can be updated
  * @param roi roi region, default be [0, 0, 0, 0]
  */
  virtual readMediaStatus_t processMediaContent(const std::string& buf, std::string& content,
                                   HceDatabaseMeta& meta, TimeStamp_t& timeMeta, hva::hvaROI_t& roi, unsigned order = 0);
  
  MediaReader m_reader;
  std::string m_mediaType;
  std::string m_dataSource;
  int m_readBufferSize;
};

}  // namespace inference

}  // namespace ai

}  // namespace hce
#endif /*__LOCAL_MEDIA_INPUT_NODE_H_*/
