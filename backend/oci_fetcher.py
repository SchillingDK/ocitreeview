"""
OCI resource fetcher. Builds the full nested tree structure for each region.
Uses the default OCI config (~/.oci/config).
"""
from __future__ import annotations

import logging
from datetime import datetime
import oci
from oci_links import (
    adb_link, block_volume_backup_link, block_volume_link, boot_volume_backup_link,
    boot_volume_link, bucket_link, compartment_link, db_backup_link, db_home_link,
    db_system_link, drg_link, filesystem_link, instance_link, internet_gateway_link,
    key_link, load_balancer_link, mount_target_link, mysql_db_link, nat_gateway_link,
    nlb_link, node_pool_link, nsg_link, oke_cluster_link, policy_link,
    route_table_link, security_list_link, service_gateway_link, subnet_link,
    vault_link, vcn_link, volume_group_link, volume_group_backup_link,
)

LIFECYCLE_ACTIVE = {"ACTIVE", "AVAILABLE", "RUNNING", "PROVISIONING", "UPDATING"}
TERMINAL_STATES = {"TERMINATED", "DELETED"}
FAILED_BACKUP_STATES = {"FAULTY", "FAILED", "ERROR"}
BACKUP_NODE_TYPES = {
    "BootVolumeBackup", "BlockVolumeBackup", "VolumeGroupBackup",
    "DBBackup", "ADBBackup", "MySQLBackup",
}

PROTOCOL_MAP = {"1": "ICMP", "6": "TCP", "17": "UDP", "58": "ICMPv6"}

log = logging.getLogger("oci_fetcher")


def _fmt_date(dt) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M UTC") if hasattr(dt, "strftime") else str(dt)


def _g(obj, attr, default=None):
    """Safe getattr for OCI SDK summary objects which may omit optional fields."""
    return getattr(obj, attr, default)


def _det(**kwargs) -> dict:
    """Build a details dict, omitting None values."""
    return {k: str(v) for k, v in kwargs.items() if v is not None}


def _fmt_ports(opts) -> str:
    """Return ':port' or ':min-max' string from TCP/UDP options, or empty string."""
    if opts is None:
        return ""
    dpr = _g(opts, "destination_port_range")
    if dpr:
        lo, hi = _g(dpr, "min"), _g(dpr, "max")
        return f":{lo}" if lo == hi else f":{lo}-{hi}"
    return ""


def _node(id: str, name: str, type: str, link: str | None = None, children: list | None = None,
          time_created=None, details: dict | None = None, failed: bool = False,
          no_backup: bool = False) -> dict:
    return {
        "id": id,
        "name": name,
        "type": type,
        "link": link,
        "children": children or [],
        "time_created": _fmt_date(time_created),
        "details": details or {},
        "failed": failed,
        "no_backup": no_backup,
    }


def _safe(fn, *args, **kwargs):
    """Call an OCI SDK function, return empty list on error and log it.
    Handles both plain-list responses and Collection objects (e.g. NLB)."""
    try:
        data = fn(*args, **kwargs).data
        # Some APIs (e.g. NetworkLoadBalancer) return a Collection wrapper with .items
        if hasattr(data, "items"):
            return data.items
        return data
    except Exception as exc:
        log.warning("OCI call %s failed: %s", fn.__qualname__, exc)
        return []


# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------

def _fetch_vcns(net_client, region, compartment_id):
    vcns = _safe(net_client.list_vcns, compartment_id=compartment_id)
    nodes = []
    for vcn in vcns:
        if vcn.lifecycle_state in TERMINAL_STATES:
            continue
        children = []

        # Subnets
        subnets = _safe(net_client.list_subnets, compartment_id=compartment_id, vcn_id=vcn.id)
        for s in subnets:
            if s.lifecycle_state in TERMINAL_STATES:
                continue
            children.append(_node(s.id, s.display_name, "Subnet", subnet_link(region, s.id),
                time_created=_g(s, "time_created"),
                details=_det(
                    cidr_block=_g(s, "cidr_block"),
                    availability_domain=_g(s, "availability_domain"),
                    dns_label=_g(s, "dns_label"),
                    lifecycle_state=s.lifecycle_state,
                    prohibit_public_ip=_g(s, "prohibit_public_ip_on_vnic"),
                )))

        # Security Lists
        sls = _safe(net_client.list_security_lists, compartment_id=compartment_id, vcn_id=vcn.id)
        for s in sls:
            if s.lifecycle_state in TERMINAL_STATES:
                continue
            ingress_rules = _g(s, "ingress_security_rules") or []
            egress_rules = _g(s, "egress_security_rules") or []
            rule_nodes = []
            for idx, r in enumerate(ingress_rules):
                proto_str = str(_g(r, "protocol", "all"))
                protocol = PROTOCOL_MAP.get(proto_str, "All" if proto_str == "all" else f"Proto {proto_str}")
                ports = _fmt_ports(_g(r, "tcp_options")) or _fmt_ports(_g(r, "udp_options"))
                rule_nodes.append(_node(
                    f"{s.id}-ingress-{idx}",
                    f"← {protocol}{ports} from {_g(r, 'source') or 'any'}",
                    "SecurityListRule", None,
                    details=_det(
                        direction="INGRESS",
                        protocol=protocol,
                        source=_g(r, "source"),
                        source_type=_g(r, "source_type"),
                        ports=ports.lstrip(":") or None,
                        is_stateless=_g(r, "is_stateless"),
                        description=_g(r, "description"),
                    )
                ))
            for idx, r in enumerate(egress_rules):
                proto_str = str(_g(r, "protocol", "all"))
                protocol = PROTOCOL_MAP.get(proto_str, "All" if proto_str == "all" else f"Proto {proto_str}")
                ports = _fmt_ports(_g(r, "tcp_options")) or _fmt_ports(_g(r, "udp_options"))
                rule_nodes.append(_node(
                    f"{s.id}-egress-{idx}",
                    f"→ {protocol}{ports} to {_g(r, 'destination') or 'any'}",
                    "SecurityListRule", None,
                    details=_det(
                        direction="EGRESS",
                        protocol=protocol,
                        destination=_g(r, "destination"),
                        destination_type=_g(r, "destination_type"),
                        ports=ports.lstrip(":") or None,
                        is_stateless=_g(r, "is_stateless"),
                        description=_g(r, "description"),
                    )
                ))
            children.append(_node(s.id, s.display_name, "SecurityList", security_list_link(region, s.id),
                rule_nodes,
                time_created=_g(s, "time_created"),
                details=_det(
                    lifecycle_state=s.lifecycle_state,
                    ingress_rules=len(ingress_rules),
                    egress_rules=len(egress_rules),
                )))

        # NSGs
        nsgs = _safe(net_client.list_network_security_groups, compartment_id=compartment_id, vcn_id=vcn.id)
        for n in nsgs:
            if n.lifecycle_state in TERMINAL_STATES:
                continue
            nsg_rules = _safe(net_client.list_network_security_group_security_rules, n.id)
            rule_nodes = []
            ingress_count = egress_count = 0
            for rule in nsg_rules:
                direction = _g(rule, "direction", "?")
                if direction == "INGRESS":
                    ingress_count += 1
                else:
                    egress_count += 1
                proto_str = str(_g(rule, "protocol", "all"))
                protocol = PROTOCOL_MAP.get(proto_str, "All" if proto_str == "all" else f"Proto {proto_str}")
                tcp_opts = _g(rule, "tcp_options")
                udp_opts = _g(rule, "udp_options")
                ports = _fmt_ports(tcp_opts) or _fmt_ports(udp_opts)
                if direction == "INGRESS":
                    endpoint = _g(rule, "source") or "any"
                    arrow = "←"
                    endpoint_label = f"from {endpoint}"
                else:
                    endpoint = _g(rule, "destination") or "any"
                    arrow = "→"
                    endpoint_label = f"to {endpoint}"
                stateless = _g(rule, "is_stateless")
                name_parts = [arrow, protocol + ports, endpoint_label]
                if stateless:
                    name_parts.append("(stateless)")
                rule_nodes.append(_node(
                    rule.id,
                    " ".join(name_parts),
                    "NSGRule",
                    None,
                    time_created=_g(rule, "time_created"),
                    details=_det(
                        direction=direction,
                        protocol=protocol,
                        source=_g(rule, "source"),
                        source_type=_g(rule, "source_type"),
                        destination=_g(rule, "destination"),
                        destination_type=_g(rule, "destination_type"),
                        ports=ports.lstrip(":") or None,
                        is_stateless=stateless,
                        description=_g(rule, "description"),
                    )
                ))
            children.append(_node(n.id, n.display_name, "NSG", nsg_link(region, n.id),
                rule_nodes,
                time_created=_g(n, "time_created"),
                details=_det(
                    lifecycle_state=n.lifecycle_state,
                    ingress_rules=ingress_count,
                    egress_rules=egress_count,
                )))

        # Route Tables
        rts = _safe(net_client.list_route_tables, compartment_id=compartment_id, vcn_id=vcn.id)
        for r in rts:
            if r.lifecycle_state in TERMINAL_STATES:
                continue
            children.append(_node(r.id, r.display_name, "RouteTable", route_table_link(region, r.id),
                time_created=_g(r, "time_created"),
                details=_det(lifecycle_state=r.lifecycle_state)))

        # Internet Gateways
        igs = _safe(net_client.list_internet_gateways, compartment_id=compartment_id, vcn_id=vcn.id)
        for g in igs:
            if g.lifecycle_state in TERMINAL_STATES:
                continue
            children.append(_node(g.id, g.display_name, "InternetGateway", internet_gateway_link(region, g.id),
                time_created=_g(g, "time_created"),
                details=_det(is_enabled=_g(g, "is_enabled"), lifecycle_state=g.lifecycle_state)))

        # NAT Gateways
        nats = _safe(net_client.list_nat_gateways, compartment_id=compartment_id, vcn_id=vcn.id)
        for n in nats:
            if n.lifecycle_state in TERMINAL_STATES:
                continue
            children.append(_node(n.id, n.display_name, "NATGateway", nat_gateway_link(region, n.id),
                time_created=_g(n, "time_created"),
                details=_det(nat_ip=_g(n, "nat_ip"), block_traffic=_g(n, "block_traffic"), lifecycle_state=n.lifecycle_state)))

        # Service Gateways
        sgs = _safe(net_client.list_service_gateways, compartment_id=compartment_id, vcn_id=vcn.id)
        for g in sgs:
            if g.lifecycle_state in TERMINAL_STATES:
                continue
            children.append(_node(g.id, g.display_name, "ServiceGateway", service_gateway_link(region, g.id),
                time_created=_g(g, "time_created"),
                details=_det(block_traffic=_g(g, "block_traffic"), lifecycle_state=g.lifecycle_state)))

        # DRGs attached to this VCN
        drg_attachments = _safe(net_client.list_drg_attachments, compartment_id=compartment_id, vcn_id=vcn.id)
        for da in drg_attachments:
            if da.lifecycle_state in TERMINAL_STATES:
                continue
            try:
                drg = net_client.get_drg(da.drg_id).data
                children.append(_node(drg.id, drg.display_name, "DRG", drg_link(region, drg.id),
                    time_created=drg.time_created,
                    details=_det(lifecycle_state=drg.lifecycle_state)))
            except Exception:
                pass

        cidr = ", ".join(_g(vcn, "cidr_blocks") or [_g(vcn, "cidr_block", "")])
        nodes.append(_node(vcn.id, vcn.display_name, "VCN", vcn_link(region, vcn.id), children,
            time_created=_g(vcn, "time_created"),
            details=_det(cidr_blocks=cidr or None, dns_label=_g(vcn, "dns_label"), lifecycle_state=vcn.lifecycle_state)))
    return nodes


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

def _fetch_instances(compute_client, block_client, region, compartment_id):
    instances = _safe(compute_client.list_instances, compartment_id=compartment_id)
    nodes = []
    for inst in instances:
        if inst.lifecycle_state in TERMINAL_STATES:
            continue
        children = []

        # Boot volumes
        bv_attachments = _safe(
            compute_client.list_boot_volume_attachments,
            inst.availability_domain, compartment_id, instance_id=inst.id
        )
        for bva in bv_attachments:
            if bva.lifecycle_state in TERMINAL_STATES:
                continue
            try:
                bv = block_client.get_boot_volume(bva.boot_volume_id).data
                bv_children = []
                backups = _safe(block_client.list_boot_volume_backups, compartment_id=compartment_id, boot_volume_id=bv.id)
                for b in backups:
                    if b.lifecycle_state in TERMINAL_STATES:
                        continue
                    bv_children.append(_node(b.id, b.display_name, "BootVolumeBackup",
                        boot_volume_backup_link(region, b.id),
                        time_created=_g(b, "time_created"),
                        details=_det(type=_g(b, "type"), lifecycle_state=b.lifecycle_state,
                                     size_in_gbs=_g(b, "size_in_gbs"),
                                     unique_size_in_gbs=_g(b, "unique_size_in_gbs"),
                                     expiration_time=_fmt_date(_g(b, "expiration_time"))),
                        failed=b.lifecycle_state in FAILED_BACKUP_STATES))
                children.append(_node(bv.id, bv.display_name, "BootVolume",
                    boot_volume_link(region, bv.id), bv_children,
                    time_created=_g(bv, "time_created"),
                    details=_det(size_in_gbs=_g(bv, "size_in_gbs"),
                                 vpus_per_gb=_g(bv, "vpus_per_gb"),
                                 lifecycle_state=bv.lifecycle_state,
                                 availability_domain=_g(bv, "availability_domain")),
                    no_backup=not bv_children))
            except Exception:
                pass

        # Block volumes
        vol_attachments = _safe(
            compute_client.list_volume_attachments,
            compartment_id, instance_id=inst.id
        )
        for va in vol_attachments:
            if va.lifecycle_state in TERMINAL_STATES:
                continue
            try:
                vol = block_client.get_volume(va.volume_id).data
                vol_children = []
                backups = _safe(block_client.list_volume_backups, compartment_id=compartment_id, volume_id=vol.id)
                for b in backups:
                    if b.lifecycle_state in TERMINAL_STATES:
                        continue
                    vol_children.append(_node(b.id, b.display_name, "BlockVolumeBackup",
                        block_volume_backup_link(region, b.id),
                        time_created=_g(b, "time_created"),
                        details=_det(type=_g(b, "type"), lifecycle_state=b.lifecycle_state,
                                     size_in_gbs=_g(b, "size_in_gbs"),
                                     unique_size_in_gbs=_g(b, "unique_size_in_gbs"),
                                     expiration_time=_fmt_date(_g(b, "expiration_time"))),
                        failed=b.lifecycle_state in FAILED_BACKUP_STATES))
                children.append(_node(vol.id, vol.display_name, "BlockVolume",
                    block_volume_link(region, vol.id), vol_children,
                    time_created=_g(vol, "time_created"),
                    details=_det(size_in_gbs=_g(vol, "size_in_gbs"),
                                 vpus_per_gb=_g(vol, "vpus_per_gb"),
                                 lifecycle_state=vol.lifecycle_state,
                                 availability_domain=_g(vol, "availability_domain")),
                    no_backup=not vol_children))
            except Exception:
                pass

        nodes.append(_node(inst.id, inst.display_name, "Instance",
            instance_link(region, inst.id), children,
            time_created=_g(inst, "time_created"),
            details=_det(shape=_g(inst, "shape"), availability_domain=_g(inst, "availability_domain"),
                         fault_domain=_g(inst, "fault_domain"), lifecycle_state=inst.lifecycle_state,
                         region=_g(inst, "region"))))
    return nodes


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _fetch_storage(block_client, object_client, fss_client, region, compartment_id, availability_domains):
    nodes = []

    # Block volumes (standalone / unattached)
    vols = _safe(block_client.list_volumes, compartment_id=compartment_id)
    for vol in vols:
        if vol.lifecycle_state in TERMINAL_STATES:
            continue
        vol_children = []
        backups = _safe(block_client.list_volume_backups, compartment_id=compartment_id, volume_id=vol.id)
        for b in backups:
            if b.lifecycle_state in TERMINAL_STATES:
                continue
            vol_children.append(_node(b.id, b.display_name, "BlockVolumeBackup",
                block_volume_backup_link(region, b.id),
                time_created=_g(b, "time_created"),
                details=_det(type=_g(b, "type"), lifecycle_state=b.lifecycle_state,
                             size_in_gbs=_g(b, "size_in_gbs"),
                             unique_size_in_gbs=_g(b, "unique_size_in_gbs"),
                             expiration_time=_fmt_date(_g(b, "expiration_time"))),
                failed=b.lifecycle_state in FAILED_BACKUP_STATES))
        nodes.append(_node(vol.id, vol.display_name, "BlockVolume",
            block_volume_link(region, vol.id), vol_children,
            time_created=_g(vol, "time_created"),
            details=_det(size_in_gbs=_g(vol, "size_in_gbs"),
                         vpus_per_gb=_g(vol, "vpus_per_gb"),
                         lifecycle_state=vol.lifecycle_state,
                         availability_domain=_g(vol, "availability_domain")),
            no_backup=not vol_children))

    # Volume Groups
    vgs = _safe(block_client.list_volume_groups, compartment_id=compartment_id)
    for vg in vgs:
        if vg.lifecycle_state in TERMINAL_STATES:
            continue
        vg_children = []
        vg_backups = _safe(block_client.list_volume_group_backups, compartment_id=compartment_id, volume_group_id=vg.id)
        for b in vg_backups:
            if b.lifecycle_state in TERMINAL_STATES:
                continue
            vg_children.append(_node(b.id, b.display_name, "VolumeGroupBackup",
                volume_group_backup_link(region, b.id),
                time_created=_g(b, "time_created"),
                details=_det(type=_g(b, "type"), lifecycle_state=b.lifecycle_state,
                             size_in_gbs=_g(b, "size_in_gbs"),
                             unique_size_in_gbs=_g(b, "unique_size_in_gbs")),
                failed=b.lifecycle_state in FAILED_BACKUP_STATES))
        vol_count = len(_g(vg, "volume_ids") or [])
        nodes.append(_node(vg.id, vg.display_name, "VolumeGroup",
            volume_group_link(region, vg.id), vg_children,
            time_created=_g(vg, "time_created"),
            details=_det(size_in_gbs=_g(vg, "size_in_gbs"), lifecycle_state=vg.lifecycle_state,
                         volume_count=vol_count or None,
                         availability_domain=_g(vg, "availability_domain")),
            no_backup=not vg_children))

    # Object storage
    try:
        namespace = object_client.get_namespace(compartment_id=compartment_id).data
        buckets = _safe(object_client.list_buckets, namespace, compartment_id)
        for bucket in buckets:
            nodes.append(_node(
                f"bucket-{bucket.name}", bucket.name, "Bucket",
                bucket_link(region, namespace, bucket.name),
                time_created=_g(bucket, "time_created"),
                details=_det(storage_tier=_g(bucket, "storage_tier"), namespace=namespace)))
    except Exception:
        pass

    # File systems & mount targets (per AD)
    for ad in availability_domains:
        filesystems = _safe(fss_client.list_file_systems, compartment_id=compartment_id, availability_domain=ad.name)
        for fs in filesystems:
            if fs.lifecycle_state in TERMINAL_STATES:
                continue
            nodes.append(_node(fs.id, fs.display_name, "FileSystem",
                filesystem_link(region, fs.id),
                time_created=_g(fs, "time_created"),
                details=_det(lifecycle_state=fs.lifecycle_state,
                             metered_bytes=_g(fs, "metered_bytes"),
                             availability_domain=ad.name)))

        mts = _safe(fss_client.list_mount_targets, compartment_id=compartment_id, availability_domain=ad.name)
        for mt in mts:
            if mt.lifecycle_state in TERMINAL_STATES:
                continue
            nodes.append(_node(mt.id, mt.display_name, "MountTarget",
                mount_target_link(region, mt.id),
                time_created=_g(mt, "time_created"),
                details=_det(lifecycle_state=mt.lifecycle_state,
                             hostname_label=_g(mt, "hostname_label"),
                             availability_domain=ad.name)))

    return nodes


# ---------------------------------------------------------------------------
# Databases
# ---------------------------------------------------------------------------

def _fetch_databases(db_client, mysql_client, mysql_backup_client, region, compartment_id):
    nodes = []

    # DB Systems (bare metal / VM / Exadata)
    db_systems = _safe(db_client.list_db_systems, compartment_id=compartment_id)
    for dbs in db_systems:
        if dbs.lifecycle_state in TERMINAL_STATES:
            continue
        children = []
        db_homes = _safe(db_client.list_db_homes, compartment_id=compartment_id, db_system_id=dbs.id)
        for home in db_homes:
            if home.lifecycle_state in TERMINAL_STATES:
                continue
            home_children = []
            databases = _safe(db_client.list_databases, compartment_id=compartment_id, db_home_id=home.id)
            for db in databases:
                if db.lifecycle_state in TERMINAL_STATES:
                    continue
                backups = _safe(db_client.list_backups, database_id=db.id)
                backup_nodes = []
                for b in backups:
                    if b.lifecycle_state in TERMINAL_STATES:
                        continue
                    backup_nodes.append(_node(b.id, b.display_name, "DBBackup",
                        db_backup_link(region, b.id),
                        time_created=getattr(b, "time_created", None),
                        details=_det(type=getattr(b, "type", None),
                                     lifecycle_state=b.lifecycle_state,
                                     database_size_in_gbs=getattr(b, "database_size_in_gbs", None)),
                        failed=b.lifecycle_state in FAILED_BACKUP_STATES))
                home_children.append(_node(db.id, db.db_name, "Database",
                    db_home_link(region, home.id), backup_nodes,
                    time_created=_g(db, "time_created"),
                    details=_det(db_version=_g(db, "db_version"), lifecycle_state=db.lifecycle_state,
                                 db_unique_name=_g(db, "db_unique_name")),
                    no_backup=not backup_nodes))
            children.append(_node(home.id, home.display_name, "DBHome",
                db_home_link(region, home.id), home_children,
                time_created=_g(home, "time_created"),
                details=_det(db_version=_g(home, "db_version"), lifecycle_state=home.lifecycle_state)))
        nodes.append(_node(dbs.id, dbs.display_name, "DBSystem",
            db_system_link(region, dbs.id), children,
            time_created=_g(dbs, "time_created"),
            details=_det(shape=_g(dbs, "shape"),
                         availability_domain=_g(dbs, "availability_domain"),
                         lifecycle_state=dbs.lifecycle_state,
                         version=_g(dbs, "version"),
                         node_count=_g(dbs, "node_count"),
                         data_storage_size_in_gbs=_g(dbs, "data_storage_size_in_gbs"),
                         hostname=_g(dbs, "hostname"))))

    # Autonomous Databases
    adbs = _safe(db_client.list_autonomous_databases, compartment_id=compartment_id)
    for adb in adbs:
        if adb.lifecycle_state in TERMINAL_STATES:
            continue
        backups = _safe(db_client.list_autonomous_database_backups, autonomous_database_id=adb.id)
        backup_nodes = []
        for b in backups:
            if b.lifecycle_state in TERMINAL_STATES:
                continue
            backup_nodes.append(_node(b.id, getattr(b, "display_name", None) or b.id, "ADBBackup", None,
                time_created=getattr(b, "time_created", None),
                details=_det(type=getattr(b, "type", None),
                             lifecycle_state=b.lifecycle_state,
                             is_automatic=getattr(b, "is_automatic", None)),
                failed=b.lifecycle_state in FAILED_BACKUP_STATES))
        nodes.append(_node(adb.id, adb.display_name, "AutonomousDB",
            adb_link(region, adb.id), backup_nodes,
            time_created=_g(adb, "time_created"),
            details=_det(db_version=_g(adb, "db_version"),
                         cpu_core_count=_g(adb, "cpu_core_count"),
                         data_storage_size_in_tbs=_g(adb, "data_storage_size_in_tbs"),
                         db_workload=_g(adb, "db_workload"),
                         lifecycle_state=adb.lifecycle_state,
                         is_auto_scaling_enabled=_g(adb, "is_auto_scaling_enabled")),
            no_backup=not backup_nodes))

    # MySQL DB Systems
    mysql_systems = _safe(mysql_client.list_db_systems, compartment_id=compartment_id)
    for ms in mysql_systems:
        if ms.lifecycle_state in TERMINAL_STATES:
            continue
        backups = _safe(mysql_backup_client.list_backups, compartment_id=compartment_id, db_system_id=ms.id)
        backup_nodes = []
        for b in backups:
            if b.lifecycle_state in TERMINAL_STATES:
                continue
            backup_nodes.append(_node(b.id, b.display_name, "MySQLBackup", None,
                time_created=getattr(b, "time_created", None),
                details=_det(backup_type=getattr(b, "backup_type", None),
                             lifecycle_state=b.lifecycle_state,
                             mysql_version=getattr(b, "mysql_version", None),
                             data_storage_size_in_gbs=getattr(b, "data_storage_size_in_gbs", None)),
                failed=b.lifecycle_state in FAILED_BACKUP_STATES))
        endpoints = ", ".join(
            f"{e.ip_address}:{e.port}" for e in (getattr(ms, "endpoints", None) or [])
            if getattr(e, "ip_address", None)
        ) or None
        nodes.append(_node(ms.id, ms.display_name, "MySQLDB",
            mysql_db_link(region, ms.id), backup_nodes,
            time_created=_g(ms, "time_created"),
            details=_det(mysql_version=_g(ms, "mysql_version"),
                         shape_name=_g(ms, "shape_name"),
                         lifecycle_state=ms.lifecycle_state, endpoints=endpoints),
            no_backup=not backup_nodes))

    return nodes


# ---------------------------------------------------------------------------
# Load Balancers
# ---------------------------------------------------------------------------

def _fetch_load_balancers(lb_client, nlb_client, region, compartment_id):
    nodes = []
    lbs = _safe(lb_client.list_load_balancers, compartment_id=compartment_id)
    for lb in lbs:
        if lb.lifecycle_state in TERMINAL_STATES:
            continue
        ips = ", ".join(a.ip_address for a in (_g(lb, "ip_addresses") or []) if _g(a, "ip_address")) or None
        nodes.append(_node(lb.id, lb.display_name, "LoadBalancer",
            load_balancer_link(region, lb.id),
            time_created=_g(lb, "time_created"),
            details=_det(shape_name=_g(lb, "shape_name"), lifecycle_state=lb.lifecycle_state,
                         ip_addresses=ips, is_private=_g(lb, "is_private"))))

    nlbs = _safe(nlb_client.list_network_load_balancers, compartment_id=compartment_id)
    for nlb in nlbs:
        if nlb.lifecycle_state in TERMINAL_STATES:
            continue
        ips = ", ".join(a.ip_address for a in (_g(nlb, "ip_addresses") or []) if _g(a, "ip_address")) or None
        nodes.append(_node(nlb.id, nlb.display_name, "NetworkLoadBalancer",
            nlb_link(region, nlb.id),
            time_created=_g(nlb, "time_created"),
            details=_det(lifecycle_state=nlb.lifecycle_state,
                         ip_addresses=ips, is_private=_g(nlb, "is_private"))))
    return nodes


# ---------------------------------------------------------------------------
# OKE
# ---------------------------------------------------------------------------

def _fetch_oke(oke_client, region, compartment_id):
    nodes = []
    clusters = _safe(oke_client.list_clusters, compartment_id=compartment_id)
    for cluster in clusters:
        if cluster.lifecycle_state in TERMINAL_STATES:
            continue
        pools = _safe(oke_client.list_node_pools, compartment_id=compartment_id, cluster_id=cluster.id)
        pool_nodes = []
        for p in pools:
            if p.lifecycle_state in TERMINAL_STATES:
                continue
            node_count = getattr(getattr(p, "node_config_details", None), "size", None)
            pool_nodes.append(_node(p.id, p.name, "NodePool",
                node_pool_link(region, p.id),
                time_created=_g(p, "time_created"),
                details=_det(node_shape=_g(p, "node_shape"), node_count=node_count,
                             kubernetes_version=_g(p, "kubernetes_version"),
                             lifecycle_state=p.lifecycle_state)))
        endpoints = _g(cluster, "endpoints")
        nodes.append(_node(cluster.id, cluster.name, "OKECluster",
            oke_cluster_link(region, cluster.id), pool_nodes,
            time_created=_g(cluster, "time_created"),
            details=_det(kubernetes_version=_g(cluster, "kubernetes_version"),
                         lifecycle_state=cluster.lifecycle_state,
                         endpoint=_g(endpoints, "kubernetes") if endpoints else None)))
    return nodes


# ---------------------------------------------------------------------------
# Security / Identity
# ---------------------------------------------------------------------------

def _fetch_security(kms_vault_client_factory, identity_client, region, compartment_id):
    nodes = []

    # Vaults
    try:
        kms_mgmt_client = oci.key_management.KmsVaultClient(oci.config.from_file())
        kms_mgmt_client.base_client.set_region(region)
        vaults = _safe(kms_mgmt_client.list_vaults, compartment_id=compartment_id)
        for vault in vaults:
            if vault.lifecycle_state in TERMINAL_STATES:
                continue
            key_children = []
            try:
                keys_client = oci.key_management.KmsManagementClient(
                    oci.config.from_file(), service_endpoint=vault.management_endpoint
                )
                keys = _safe(keys_client.list_keys, compartment_id=compartment_id)
                for k in keys:
                    if k.lifecycle_state in TERMINAL_STATES:
                        continue
                    key_shape = getattr(k, "key_shape", None)
                    key_children.append(_node(k.id, k.display_name, "Key",
                        key_link(region, vault.id, k.id),
                        time_created=k.time_created,
                        details=_det(lifecycle_state=k.lifecycle_state,
                                     algorithm=getattr(key_shape, "algorithm", None),
                                     length=getattr(key_shape, "length", None))))
            except Exception:
                pass
            nodes.append(_node(vault.id, vault.display_name, "Vault",
                vault_link(region, vault.id), key_children,
                time_created=_g(vault, "time_created"),
                details=_det(vault_type=_g(vault, "vault_type"), lifecycle_state=vault.lifecycle_state,
                             management_endpoint=_g(vault, "management_endpoint"))))
    except Exception:
        pass

    # Policies
    policies = _safe(identity_client.list_policies, compartment_id=compartment_id)
    for p in policies:
        if p.lifecycle_state in TERMINAL_STATES:
            continue
        stmt_count = len(p.statements or [])
        nodes.append(_node(p.id, p.name, "Policy",
            policy_link(region, p.id),
            time_created=_g(p, "time_created"),
            details=_det(lifecycle_state=p.lifecycle_state,
                         description=_g(p, "description"),
                         statement_count=stmt_count or None)))

    return nodes


# ---------------------------------------------------------------------------
# Compartment tree builder
# ---------------------------------------------------------------------------

def _collect_backup_stats(nodes: list) -> dict:
    """Walk the subtree and return total/failed/no_backup count and last successful backup date."""
    total = failed = no_backup = 0
    last_ok_dt: datetime | None = None
    for node in nodes:
        if node["type"] in BACKUP_NODE_TYPES:
            total += 1
            if node["failed"]:
                failed += 1
            else:
                tc = node["time_created"]
                if tc:
                    try:
                        dt = datetime.strptime(tc, "%Y-%m-%d %H:%M UTC")
                        if last_ok_dt is None or dt > last_ok_dt:
                            last_ok_dt = dt
                    except ValueError:
                        pass
        if node.get("no_backup"):
            no_backup += 1
        child = _collect_backup_stats(node["children"])
        total += child["total"]
        failed += child["failed"]
        no_backup += child["no_backup"]
        if child["last_ok"]:
            try:
                child_dt = datetime.strptime(child["last_ok"], "%Y-%m-%d %H:%M UTC")
                if last_ok_dt is None or child_dt > last_ok_dt:
                    last_ok_dt = child_dt
            except ValueError:
                pass
    return {
        "total": total,
        "failed": failed,
        "no_backup": no_backup,
        "last_ok": last_ok_dt.strftime("%Y-%m-%d %H:%M UTC") if last_ok_dt else None,
    }


def _build_compartment_tree(
    compartment_id: str,
    all_compartments: list,
    region: str,
    config: dict,
    clients: dict,
) -> list:
    children_compartments = [c for c in all_compartments if c.compartment_id == compartment_id]
    result = []
    for comp in children_compartments:
        if comp.lifecycle_state in TERMINAL_STATES:
            continue

        log.info("  Scanning compartment: %s (%s)", comp.name, comp.id)
        availability_domains = _safe(clients["identity"].list_availability_domains, comp.id)

        resource_groups = {
            "Networking": _fetch_vcns(clients["network"], region, comp.id),
            "Compute": _fetch_instances(clients["compute"], clients["block"], region, comp.id),
            "Storage": _fetch_storage(
                clients["block"], clients["object"], clients["fss"],
                region, comp.id, availability_domains
            ),
            "Databases": _fetch_databases(clients["db"], clients["mysql"], clients["mysql_backup"], region, comp.id),
            "LoadBalancers": _fetch_load_balancers(clients["lb"], clients["nlb"], region, comp.id),
            "Kubernetes": _fetch_oke(clients["oke"], region, comp.id),
            "Security": _fetch_security(None, clients["identity"], region, comp.id),
        }

        group_nodes = [
            _node(f"{comp.id}-{group_name}", group_name, "Group", None, items)
            for group_name, items in resource_groups.items()
            if items
        ]

        # Recurse into child compartments
        nested = _build_compartment_tree(comp.id, all_compartments, region, config, clients)

        all_children = nested + group_nodes
        backup_stats = _collect_backup_stats(all_children)
        comp_details = _det(
            description=getattr(comp, "description", None),
            lifecycle_state=comp.lifecycle_state,
        )
        if backup_stats["total"] > 0:
            comp_details["backup_total"] = str(backup_stats["total"])
            comp_details["backup_failed"] = str(backup_stats["failed"])
            if backup_stats["last_ok"]:
                comp_details["backup_last_ok"] = backup_stats["last_ok"]
        if backup_stats["no_backup"] > 0:
            comp_details["backup_no_backup"] = str(backup_stats["no_backup"])

        comp_node = _node(
            comp.id,
            comp.name,
            "Compartment",
            compartment_link(region, comp.id),
            all_children,
            time_created=getattr(comp, "time_created", None),
            details=comp_details,
            failed=backup_stats["failed"] > 0,
            no_backup=backup_stats["no_backup"] > 0,
        )
        result.append(comp_node)
    return result


# ---------------------------------------------------------------------------
# Tree pruning
# ---------------------------------------------------------------------------

def _prune_empty(nodes: list) -> list:
    """Recursively remove Group nodes with no resources and Compartment nodes
    that are entirely empty after pruning. Other node types are kept as-is."""
    result = []
    for node in nodes:
        t = node["type"]
        if t == "Group":
            if node["children"]:
                result.append(node)
            # else: drop empty resource group
        elif t == "Compartment":
            pruned = _prune_empty(node["children"])
            if pruned:
                result.append({**node, "children": pruned})
            # else: drop empty compartment
        else:
            result.append(node)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_region_tree(region: str) -> dict:
    log.info("Starting region: %s", region)
    try:
        config = oci.config.from_file()
        config["region"] = region

        clients = {
            "identity": oci.identity.IdentityClient(config),
            "network": oci.core.VirtualNetworkClient(config),
            "compute": oci.core.ComputeClient(config),
            "block": oci.core.BlockstorageClient(config),
            "object": oci.object_storage.ObjectStorageClient(config),
            "fss": oci.file_storage.FileStorageClient(config),
            "db": oci.database.DatabaseClient(config),
            "mysql": oci.mysql.DbSystemClient(config),
            "mysql_backup": oci.mysql.DbBackupsClient(config),
            "lb": oci.load_balancer.LoadBalancerClient(config),
            "nlb": oci.network_load_balancer.NetworkLoadBalancerClient(config),
            "oke": oci.container_engine.ContainerEngineClient(config),
        }

        tenancy_id = config["tenancy"]
        all_compartments = []
        try:
            log.info("Listing all compartments in %s", region)
            paginator = oci.pagination.list_call_get_all_results(
                clients["identity"].list_compartments,
                tenancy_id,
                compartment_id_in_subtree=True,
                access_level="ACCESSIBLE",
            )
            all_compartments = paginator.data
            log.info("Found %d compartments", len(all_compartments))
        except Exception as exc:
            log.warning("Could not list compartments: %s", exc)

        tree = _build_compartment_tree(tenancy_id, all_compartments, region, config, clients)
        tree = _prune_empty(tree)
        log.info("Finished region: %s — %d top-level compartments (after pruning)", region, len(tree))
        return {"region": region, "children": tree, "error": None}
    except Exception as exc:
        log.error("Fatal error building tree for region %s: %s", region, exc, exc_info=True)
        return {"region": region, "children": [], "error": str(exc)}
