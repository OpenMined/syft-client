# Syft Client

Syft client is a high level client object bundling modular components which enable a user to execute map/reduce bash scripts (and any file-based resources those bash scripts might require) across a decentralized, peer-to-peer network of computers... connected through whichever transport layers those organizations already trust (e.g. Google Drive, Dropbox, etc.). 

# Principles

- File-first: State in first and foremost described by files, which are synced amongst peers on the network to communicate updates to state. State can also be stored in more performant ways (e.g. client or server side databases, indexes, etc.) but this is secondary for performance, and is an optional part of the system. All state is first-and-foremost made available as a file (future development may explore in-memory file storage...akin to the relationship between Hadoop's HDFS and Spark's upgrade to in-memory storage over HDFS).
- Offline-first: Datasites (i.e. computers/users/peers) in the syft network can go offline/online as desired and all functionality continues to work, as messages from that server are cached locally when it is offline, and messages to each server are cached in the transport layers (e.g. Google Drive) until that datasite comes back online. Datasites can use faster, ephemeral transport layers when datasites are online at the same time (e.g. WebRTC), but this is an optional upgrade, not the foundation to the system.
- Shell-first: Functions are first and foremost described as shell scripts (run.sh) inside of a folder of resources (job_23j3ijgw/).
