#bool bSentOnce

uint64 mn_id # unique MP id
uint8 mn_client_id # client id
#uint32 mUniqueId
#uint64 mn_first_keyframe_id
#uint8 mnFirstKfClientId

#bool mbAck

#Position in absolute coordinates
float32[3] mv_position
     #float32[3] mPosPar
     #bool mbPoseChanged

     #bool mbServerBA

#Keyframes observing the point and associated index in keyframe
uint64[] mv_observation_keyframe_ids
     #uint8[] mObservations_KFClientIDs
uint16[] mv_observations_n

#Mean viewing direction
float32[] mv_normal_vector
     #bool mbNormalAndDepthChanged

#Best descriptor to fast matching
     # uint8[32] mDescriptor
Descriptor[] mv_descriptors

#Reference KeyFrame
     #uint32 mpPredKFId
     #uint8 mpPredKFClientId
     #uint32 mpParKFId
     #uint8 mpParKFClientId

#Bad flag
     #bool mbBad

#Scale invariance distances
float32 mf_min_distance
float32 mf_max_distance

#Visualization
     #bool mbMultiUse


#bool mbNewCreated   # obsolete - not used anymore
uint8 mn_num_observable
uint8 mn_num_observed

#bool mbWill_be_erased
uint64 mn_refer_keyframe_id
uint64 mn_observed_in_other_keyframe_id
uint32 mn_observed_in_other_keyframe_index
uint64 mn_replace_other_id

