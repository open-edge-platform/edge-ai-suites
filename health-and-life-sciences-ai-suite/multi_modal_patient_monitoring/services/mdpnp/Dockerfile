FROM eclipse-temurin:17

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

ENV http_proxy=${http_proxy:-$HTTP_PROXY} \
	https_proxy=${https_proxy:-$HTTPS_PROXY} \
	no_proxy=${no_proxy:-$NO_PROXY} \
	HTTP_PROXY=${HTTP_PROXY:-$http_proxy} \
	HTTPS_PROXY=${HTTPS_PROXY:-$https_proxy} \
	NO_PROXY=${NO_PROXY:-$no_proxy}
COPY mdpnp/interop-lab/demo-apps/flat /opt/mdpnp/flat
WORKDIR /opt/mdpnp/flat
ENV LD_LIBRARY_PATH /opt/mdpnp/flat
ENV RTI_LICENSE_FILE /opt/mdpnp/flat/OpenICE_license.dat

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]