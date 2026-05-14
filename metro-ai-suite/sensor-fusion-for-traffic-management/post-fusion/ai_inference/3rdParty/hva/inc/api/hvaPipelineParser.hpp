#ifndef HVA_HVAPIPELINEPARSER_HPP
#define HVA_HVAPIPELINEPARSER_HPP

#include <memory>
#include <inc/util/hvaUtil.hpp>
#include <inc/api/hvaPipeline.hpp>

namespace hva{

/**
* @brief the class used to parse a json string/file describing a hva pipeline topology
* 
*/
class HVA_DECLSPEC hvaPipelineParser_t{
public: 
    hvaPipelineParser_t();

    hvaPipelineParser_t(const hvaPipelineParser_t& parser);

    hvaPipelineParser_t(hvaPipelineParser_t&& parser);

    hvaPipelineParser_t& operator=(const hvaPipelineParser_t& parser);

    hvaPipelineParser_t& operator=(hvaPipelineParser_t&& parser);

    ~hvaPipelineParser_t();

    /**
    * @brief parse a file which contains a json string describing the pipeline topology
    * 
    * @param filename path to file
    * @param[out] pipeline constructed pipeline by the file specified. Users can call 
    * hvaPipeline_t::prepare() or any following actions on this pipeline instance
    * @return hvaSuccess if success
    * 
    */
    hvaStatus_t parse(const std::string& filename, hvaPipeline_t& pipeline);

    /**
    * @brief parse a json string which describes the pipeline topology
    * 
    * @param config json string on pipeline topology
    * @param[out] pipeline constructed pipeline by the file specified. Users can call 
    * hvaPipeline_t::prepare() or any following actions on this pipeline instance
    * @return hvaSuccess if success
    * 
    */
    hvaStatus_t parseFromString(const std::string& config, hvaPipeline_t& pipeline);

private:
    /// @private
    class Impl;
    std::unique_ptr<Impl> m_impl;
};

}

#endif //#ifndef HVA_HVAPIPELINEPARSER_HPP
