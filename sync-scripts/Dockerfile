FROM alpine:latest

RUN apk add --no-cache rsync openssh-client bash

COPY sync-to-nas.sh /sync-to-nas.sh
RUN chmod +x /sync-to-nas.sh

CMD ["/sync-to-nas.sh"]
