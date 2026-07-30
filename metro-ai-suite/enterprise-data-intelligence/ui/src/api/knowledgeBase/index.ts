import request from "../request";
export const getKnowledgeBaseList = () => {
  return request({
    url: "/v1/knowledge",
    method: "get",
  });
};

export const requestKnowledgeBaseUpdate = (data: Object) => {
  return request({
    url: `/v1/knowledge/patch`,
    method: "patch",
    data,
    showLoading: true,
  });
};

export const getTokenStats = () => {
  return request({
    url: "/v1/stats",
    method: "get",
  });
};

export const requestTokenRest = () => {
  return request({
    url: "/v1/stats/reset",
    method: "post",
    showLoading: true,
    showSuccessMsg: true,
    successMsg: "monitor.resetSuccess",
  });
};
