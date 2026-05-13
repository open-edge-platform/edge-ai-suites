#ifndef HVA_HVA_HPP
#define HVA_HVA_HPP

/**
* @mainpage HVA pipeline framework 
* 
* @section intro_sec Introduction
* 
* hva pipeline framework, named from heteogeneous video analytic pipeline framework, is
* a lightweigt library that helps developers from building, managing and controlling an
* application that executes in a manner of pipelines.
*  
* @section term_sec Terms
*
* In hva, a pipeline is made up by connecting nodes to nodes, while nodes are the logic 
* representation of unit that carries on a certain work. For example, a simple video analytic
* pipeline can be made up by a decoder node followed by a detection node. Programatically, 
* nodes are interpreted as a pair of hva::hvaNode_t class and hva::hvaNodeWorker_t class in hva framework, where 
* those two are deeply binded. hva::hvaNodeWorker_t is the actual instance that does the processing
* and executes workload, while hva::hvaNode_t is more about pipeline topology and common properties
* shared by workers. Upon pipeline execution, a node can spawn multiple copies of workers
*  
* The data flow through nodes to nodes is in form of hva::hvaBlob_t, which considers as a container
* of zero or one or multiple hva::hvaBuf_t. hva::hvaBuf_t holds a piece of data, either in form of memory,
* or a fd, or anything else. There are a few child classes of hva::hvaBuf_t while users can also inherit
* from hva::hvaBuf_t to make their own types.
*
* There are six states on a hva pipeline (and its sub-components like nodes and node workers etc.),
* which are @ref idle, @ref configured, @ref prepared, @ref running, @ref depleting and @ref stop. 
* Idle is the initial state where everything remains empty. An entity, for example a node, transits
* to configured if it possesses minimum required configurations to make it preparable and runnable. 
* Pipeline reaches prepared state after user calls hva::hvaPipeline_t::prepare(), and then reaches
* running state after calling hva::hvaPipeline_t::start(). Once any entity raises an EOS event, the pipeline
* enters depleting state. This depleting state is not a stable state and it will automatically transit
* towards stop state, once the pipeline depletes its remaining unprocessed buffers.
*
* @section build_sec Build
* 
* hva depends on boost 1.75.
*
* In order to build hva from source, do
* @code{.sh}
* mkdir build && cd build
* cmake .. && make -j
* @endcode
*
* @section example_sec Example
* 
* Building and running a pipeline application with ready-to-go plugins is simple. Below is an example 
* connecting two test nodes (i.e. MyT1Node, MyT2Node).
*
* First configure the log level to debug.
* @code{.cpp}
* hvaLogger.setLogLevel(hva::hvaLogger_t::LogLevel::DEBUG);
* @endcode
* Initialize pipeline entity and nodes entities and add the nodes into pipeline
* @code{.cpp}
* hva::hvaPipeline_t pl;
*
* auto& mynode1 = pl.setSource(std::make_shared<MyT1Node>(0,1,1,"MyT1Node"), "MyT1Node");
*
* auto& mynode2 = pl.addNode(std::make_shared<MyT2Node>(1,0,1,"MyT2Node"), "MyT2Node");
* @endcode
* Then link MyT1Node out port 0 to MyT2Node in port 0
* @code{.cpp}
* pl.linkNode("MyT1Node", 0, "MyT2Node", 0);
* @endcode
* Prepare the pipeline to make it runnable.
* @code{.cpp}
* pl.prepare();
* @endcode
* Start the pipeline and block until the pipeline stop event is received. In this case 
* the pipeline will remaining running until some node raises EOS event and then pipeline 
* depletes all its remaining buffers and securely stops
* @code{.cpp}
* pl.start();
*
* std::cout<<"\nPipeline wait for event hvaEvent_PipelineStop "<<std::endl;
* pl.waitForEvent(hvaEvent_PipelineStop);
* std::cout<<"\nPipeline received event hvaEvent_PipelineStop "<<std::endl;
* @endcode  
*
*/

namespace hva{


} //namespace hva

#endif //#ifndef HVA_HVA_HPP