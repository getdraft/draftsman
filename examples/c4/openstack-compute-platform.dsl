workspace "OpenStack Compute Platform" {
  model {
    system = softwareSystem "OpenStack Compute Platform" {
      description "Core OpenStack compute, networking, and storage services that together deliver IaaS capabilities to tenant workloads."
      group "Presentation & API Layer" {
        STCK000005_RS05 = container "Cinder Block Storage Service" "Self-managed deployment of OpenStack Cinder providing persistent block storage volumes for compute instances. Runs cinde"
        STCK000001_RS01 = container "Nova Compute Service" "Self-managed deployment of OpenStack Nova providing virtual machine lifecycle management across the platform. Runs nova-"
        01KSF29JTP_9HYA = container "OpenStack API Load Balancer" "HAProxy load balancer co-located on OpenStack controller nodes. Distributes inbound API and dashboard traffic across all"
        STCK000004_RS04 = container "Neutron Networking Service" "Self-managed deployment of OpenStack Neutron providing software-defined networking for the OpenStack platform. Runs neut"
        STCK000002_RS02 = container "Keystone Identity Service" "Self-managed deployment of OpenStack Keystone providing identity, authentication, and authorization services for all Ope"
      }
      group "Data Infrastructure" {
        STCK000001_DAR1 = container "Nova Database" "MariaDB database schema dedicated to OpenStack Nova for persisting all compute service state. Stores instance records, f"
        STCK000005_DAR5 = container "Cinder Database" "MariaDB database schema dedicated to OpenStack Cinder for persisting all block storage service state. Stores volume reco"
        STCK00000D_RS0D = container "RabbitMQ Message Broker Service" "Self-managed deployment of RabbitMQ serving as the shared AMQP message broker for the OpenStack control plane. Provides "
        STCK000002_DAR2 = container "Keystone Database" "MariaDB database schema dedicated to OpenStack Keystone for persisting all identity service data. Stores users, groups, "
        STCK000004_DAR4 = container "Neutron Database" "MariaDB database schema dedicated to OpenStack Neutron for persisting all network service state. Stores virtual networks"
      }
    }
    Tenant_Workload = person "Tenant Workload" "Virtual machines and containerized workloads provisioned by Nova and managed by "
    OpenStack_Horizon_Dashboard = softwareSystem "OpenStack Horizon Dashboard" "Web UI for tenant and administrator interactions with the platform." {
      external true
    }
    External_Identity_Provider = softwareSystem "External Identity Provider" "Enterprise identity provider integrated via Keystone federation for SSO." {
      external true
    }
    01KSF29JTP_9HYA -> STCK000002_RS02 "proxies authentication requests" "HTTPS / HTTP"
    01KSF29JTP_9HYA -> STCK000004_RS04 "proxies networking API requests" "HTTPS / HTTP"
    01KSF29JTP_9HYA -> STCK000001_RS01 "proxies compute API requests" "HTTPS / HTTP"
    STCK000005_RS05 -> STCK000002_RS02 "validates tokens" "HTTP (Keystone API)"
    STCK000005_RS05 -> STCK00000D_RS0D "publishes and consumes RPC messages" "AMQP"
    STCK000005_RS05 -> STCK000005_DAR5 "persists volume state" "MySQL wire protocol"
    STCK000002_RS02 -> STCK000002_DAR2 "persists identity data" "MySQL wire protocol"
    STCK000004_RS04 -> STCK000002_RS02 "validates tokens" "HTTP (Keystone API)"
    STCK000004_RS04 -> STCK00000D_RS0D "publishes and consumes agent RPC messages" "AMQP"
    STCK000004_RS04 -> STCK000004_DAR4 "persists network state" "MySQL wire protocol"
    STCK000001_RS01 -> STCK000005_RS05 "attaches block volumes" "HTTP (Cinder API)"
    STCK000001_RS01 -> STCK000002_RS02 "validates tokens" "HTTP (Keystone API)"
    STCK000001_RS01 -> STCK00000D_RS0D "publishes and consumes RPC messages" "AMQP"
    STCK000001_RS01 -> STCK000004_RS04 "provisions network ports" "HTTP (Neutron API)"
    STCK000001_RS01 -> STCK000001_DAR1 "reads from / writes to" "MySQL wire protocol"
    STCK00000D_RS0D -> STCK000002_RS02 "calls"
  }
  views {
    container system {
      include *
      autolayout lr
    }
  }
}