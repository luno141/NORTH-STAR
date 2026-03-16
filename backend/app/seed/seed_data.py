from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.models import FederationPolicy, IngestionSource, Organization, User
from app.services.ingestion import DEFAULT_RSS
from app.services.intel import create_intel_record
from app.services.security import hash_api_key


ORG_KEYS = {
    "OrgA": "orga_admin_key",
    "OrgB": "orgb_admin_key",
    "OrgC": "orgc_admin_key",
}


def _create_orgs_and_users(db: Session) -> dict[str, Organization]:
    orgs: dict[str, Organization] = {}
    for name, key in ORG_KEYS.items():
        org = db.query(Organization).filter(Organization.name == name).first()
        if not org:
            org = Organization(name=name, api_key=key, api_key_hash=hash_api_key(key))
            db.add(org)
            db.flush()
        else:
            if not org.api_key_hash:
                org.api_key_hash = hash_api_key(key)
            if org.api_key is None:
                org.api_key = key
        orgs[name] = org

    templates = [
        ("Alice Admin", "org_admin", "alice_admin_key", "OrgA", 80),
        ("Ana Analyst", "analyst", "ana_analyst_key", "OrgA", 74),
        ("Carl Contributor", "contributor", "carl_contrib_key", "OrgA", 67),
        ("Vera Viewer", "viewer", "vera_viewer_key", "OrgA", 55),
        ("Bob Admin", "org_admin", "bob_admin_key", "OrgB", 77),
        ("Ben Analyst", "analyst", "ben_analyst_key", "OrgB", 70),
        ("Nia Contributor", "contributor", "nia_contrib_key", "OrgB", 58),
        ("Cory Admin", "org_admin", "cory_admin_key", "OrgC", 75),
        ("Chi Analyst", "analyst", "chi_analyst_key", "OrgC", 69),
        ("Moe Contributor", "contributor", "moe_contrib_key", "OrgC", 46),
    ]

    for name, role, key, org_name, rep in templates:
        u = db.query(User).filter(User.api_key_hash == hash_api_key(key)).first()
        if not u:
            db.add(
                User(
                    name=name,
                    role=role,
                    org_id=orgs[org_name].id,
                    api_key=key,
                    api_key_hash=hash_api_key(key),
                    reputation=rep,
                )
            )
        else:
            if not u.api_key_hash:
                u.api_key_hash = hash_api_key(key)
            if u.api_key is None:
                u.api_key = key
    db.flush()
    return orgs


def _seed_policies(db: Session, orgs: dict[str, Organization]) -> None:
    pairs = [
        ("OrgA", "OrgB", 55, 50),
        ("OrgA", "OrgC", 60, 60),
        ("OrgB", "OrgA", 50, 50),
        ("OrgB", "OrgC", 58, 52),
        ("OrgC", "OrgA", 62, 55),
        ("OrgC", "OrgB", 60, 45),
    ]
    for f, t, c, r in pairs:
        exists = (
            db.query(FederationPolicy)
            .filter(FederationPolicy.from_org_id == orgs[f].id, FederationPolicy.to_org_id == orgs[t].id)
            .first()
        )
        if not exists:
            db.add(
                FederationPolicy(
                    from_org_id=orgs[f].id,
                    to_org_id=orgs[t].id,
                    min_credibility=c,
                    min_reputation=r,
                    enabled=True,
                )
            )


def _seed_ingestion_sources(db: Session, orgs: dict[str, Organization]) -> None:
    def _user_by_key(key: str) -> User | None:
        return db.query(User).filter(User.api_key_hash == hash_api_key(key)).first()

    contribs = {
        "OrgA": _user_by_key("carl_contrib_key"),
        "OrgB": _user_by_key("nia_contrib_key"),
        "OrgC": _user_by_key("moe_contrib_key"),
    }

    sources = [
        {
            "name": "OrgA OpenPhish Live",
            "source_kind": "openphish",
            "org_name": "OrgA",
            "interval_minutes": 15,
            "max_rows": 250,
            "config": {"max_rows": 250},
        },
        {
            "name": "OrgB URLhaus Live",
            "source_kind": "urlhaus",
            "org_name": "OrgB",
            "interval_minutes": 20,
            "max_rows": 250,
            "config": {"max_rows": 250},
        },
        {
            "name": "OrgC Advisory RSS",
            "source_kind": "rss",
            "org_name": "OrgC",
            "interval_minutes": 30,
            "max_rows": 30,
            "config": {"urls": DEFAULT_RSS, "max_rows": 30},
        },
    ]

    for item in sources:
        exists = db.query(IngestionSource).filter(IngestionSource.name == item["name"]).first()
        if exists:
            continue
        contributor = contribs[item["org_name"]]
        db.add(
            IngestionSource(
                name=item["name"],
                source_kind=item["source_kind"],
                org_id=orgs[item["org_name"]].id,
                contributor_id=contributor.id if contributor else None,
                enabled=True,
                interval_minutes=item["interval_minutes"],
                max_rows=item["max_rows"],
                config=item["config"],
                last_status="idle",
            )
        )


def _seed_intel(db: Session, orgs: dict[str, Organization]) -> None:
    if db.query(User).count() == 0:
        return

    def _user_by_key(key: str) -> User | None:
        return db.query(User).filter(User.api_key_hash == hash_api_key(key)).first()

    contribs = {
        "OrgA": _user_by_key("carl_contrib_key"),
        "OrgB": _user_by_key("nia_contrib_key"),
        "OrgC": _user_by_key("moe_contrib_key"),
    }

    samples = [
        ("OrgA", "domain", "secure-login-alert.com", ["phishing", "credential"], "Observed phishing kit targeting payroll systems."),
        ("OrgA", "hash", "44d88612fea8a8f36de82e1278abb02f", ["malware", "worm"], "Malware hash tied to lateral movement activity."),
        ("OrgA", "url", "http://urgent-update-service.net/reset", ["phishing"], "Credential reset lure sent to finance team."),
        ("OrgB", "cve", "CVE-2025-10421", ["vuln", "rce"], "Critical RCE in public-facing middleware component."),
        ("OrgB", "ip", "185.199.110.153", ["c2", "malware"], "C2 beacon destination from EDR telemetry."),
        ("OrgB", "domain", "cdn-sync-assets[.]com", ["leak", "exfil"], "Data exfiltration staging domain seen in DNS logs."),
        ("OrgC", "email", "helpdesk@security-checks.io", ["phishing"], "Spoofed helpdesk mailbox for MFA reset scams."),
        ("OrgC", "url", "https://gist.example/leaked-creds", ["leak", "credentials"], "Potential credentials dump indexed by crawler."),
        ("OrgC", "text", "discussion on exploit reliability", ["discussion"], "Forum chatter about exploit stability, low confidence."),
    ]

    base = datetime.now(timezone.utc) - timedelta(days=2)
    for idx, (org_name, ioc_type, value, tags, context) in enumerate(samples):
        create_intel_record(
            db=db,
            org_id=orgs[org_name].id,
            contributor_id=contribs[org_name].id if contribs[org_name] else None,
            indicator_type=ioc_type,
            value=value,
            tags=tags,
            source="seed",
            timestamp=base + timedelta(hours=idx * 3),
            confidence=58 + idx * 3,
            context_text=context,
            evidence=f"Evidence packet #{idx + 1}: {context}",
        )


def seed_all(db: Session) -> None:
    orgs = _create_orgs_and_users(db)
    _seed_policies(db, orgs)
    _seed_ingestion_sources(db, orgs)
    _seed_intel(db, orgs)
    db.commit()
