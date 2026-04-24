"""
Helpers that build direct OCI console deep-links.
Regions map to their console hostnames.
"""

REGION_REALM: dict[str, str] = {
    # Commercial regions
    "eu-frankfurt-1": "Frankfurt",
    "eu-stockholm-1": "Stockholm",
}

CONSOLE_BASE = "https://cloud.oracle.com"


def _base(region: str) -> str:
    return f"{CONSOLE_BASE}?region={region}"


def compartment_link(region: str, compartment_id: str) -> str:
    return f"{CONSOLE_BASE}/identity/compartments/{compartment_id}?region={region}"


def vcn_link(region: str, vcn_id: str) -> str:
    return f"{CONSOLE_BASE}/networking/vcns/{vcn_id}?region={region}"


def subnet_link(region: str, subnet_id: str) -> str:
    return f"{CONSOLE_BASE}/networking/vcns/subnets/{subnet_id}?region={region}"


def nsg_link(region: str, nsg_id: str) -> str:
    return f"{CONSOLE_BASE}/networking/network-security-groups/{nsg_id}?region={region}"


def security_list_link(region: str, sl_id: str) -> str:
    return f"{CONSOLE_BASE}/networking/vcns/security-lists/{sl_id}?region={region}"


def route_table_link(region: str, rt_id: str) -> str:
    return f"{CONSOLE_BASE}/networking/vcns/route-tables/{rt_id}?region={region}"


def internet_gateway_link(region: str, ig_id: str) -> str:
    return f"{CONSOLE_BASE}/networking/vcns/internet-gateways/{ig_id}?region={region}"


def nat_gateway_link(region: str, nat_id: str) -> str:
    return f"{CONSOLE_BASE}/networking/vcns/nat-gateways/{nat_id}?region={region}"


def service_gateway_link(region: str, sg_id: str) -> str:
    return f"{CONSOLE_BASE}/networking/vcns/service-gateways/{sg_id}?region={region}"


def drg_link(region: str, drg_id: str) -> str:
    return f"{CONSOLE_BASE}/networking/drgs/{drg_id}?region={region}"


def instance_link(region: str, instance_id: str) -> str:
    return f"{CONSOLE_BASE}/compute/instances/{instance_id}?region={region}"


def boot_volume_link(region: str, bv_id: str) -> str:
    return f"{CONSOLE_BASE}/block-storage/boot-volumes/{bv_id}?region={region}"


def boot_volume_backup_link(region: str, bvb_id: str) -> str:
    return f"{CONSOLE_BASE}/block-storage/boot-volume-backups/{bvb_id}?region={region}"


def block_volume_link(region: str, vol_id: str) -> str:
    return f"{CONSOLE_BASE}/block-storage/volumes/{vol_id}?region={region}"


def block_volume_backup_link(region: str, vbk_id: str) -> str:
    return f"{CONSOLE_BASE}/block-storage/volume-backups/{vbk_id}?region={region}"


def bucket_link(region: str, namespace: str, bucket_name: str) -> str:
    return f"{CONSOLE_BASE}/object-storage/buckets/{namespace}/{bucket_name}?region={region}"


def filesystem_link(region: str, fs_id: str) -> str:
    return f"{CONSOLE_BASE}/fss/file-systems/{fs_id}?region={region}"


def mount_target_link(region: str, mt_id: str) -> str:
    return f"{CONSOLE_BASE}/fss/mount-targets/{mt_id}?region={region}"


def db_system_link(region: str, db_id: str) -> str:
    return f"{CONSOLE_BASE}/db/dbsystems/{db_id}?region={region}"


def db_home_link(region: str, db_home_id: str) -> str:
    return f"{CONSOLE_BASE}/db/dbhomes/{db_home_id}?region={region}"


def db_backup_link(region: str, backup_id: str) -> str:
    return f"{CONSOLE_BASE}/db/backups/{backup_id}?region={region}"


def adb_link(region: str, adb_id: str) -> str:
    return f"{CONSOLE_BASE}/db/adb/{adb_id}?region={region}"


def mysql_db_link(region: str, mysql_id: str) -> str:
    return f"{CONSOLE_BASE}/mysql/db-systems/{mysql_id}?region={region}"


def load_balancer_link(region: str, lb_id: str) -> str:
    return f"{CONSOLE_BASE}/load-balancer/load-balancers/{lb_id}?region={region}"


def nlb_link(region: str, nlb_id: str) -> str:
    return f"{CONSOLE_BASE}/load-balancer/network-load-balancers/{nlb_id}?region={region}"


def oke_cluster_link(region: str, cluster_id: str) -> str:
    return f"{CONSOLE_BASE}/containers/clusters/{cluster_id}?region={region}"


def node_pool_link(region: str, np_id: str) -> str:
    return f"{CONSOLE_BASE}/containers/node-pools/{np_id}?region={region}"


def vault_link(region: str, vault_id: str) -> str:
    return f"{CONSOLE_BASE}/security/kms/vaults/{vault_id}?region={region}"


def key_link(region: str, vault_id: str, key_id: str) -> str:
    return f"{CONSOLE_BASE}/security/kms/vaults/{vault_id}/keys/{key_id}?region={region}"


def policy_link(region: str, policy_id: str) -> str:
    return f"{CONSOLE_BASE}/identity/policies/{policy_id}?region={region}"


def volume_group_link(region: str, vg_id: str) -> str:
    return f"{CONSOLE_BASE}/block-storage/volume-groups/{vg_id}?region={region}"


def volume_group_backup_link(region: str, vgb_id: str) -> str:
    return f"{CONSOLE_BASE}/block-storage/volume-group-backups/{vgb_id}?region={region}"
