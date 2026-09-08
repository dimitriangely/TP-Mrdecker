#!/usr/bin/env python3
"""Schéma d'architecture HLD M2-Shop (PNG pour le Word)."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

OUT = Path(__file__).resolve().parents[1] / "docs" / "architecture-m2shop.png"

NAVY = "#1B3A4B"
TEAL = "#1F6F6A"
PROD = "#1E4D6B"
ADMIN = "#3D5A40"
FW = "#6B3E1E"
HOST = "#3A3A4A"
BG = "#F7F5F0"
PAPER = "#FFFEFB"


def box(ax, x, y, w, h, title, lines, fc, ec=None):
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor=fc, edgecolor=ec or NAVY, linewidth=1.4, zorder=2,
    )
    ax.add_patch(p)
    ax.text(x + w / 2, y + h - 0.22, title, ha="center", va="top",
            fontsize=10, fontweight="bold", color="white", zorder=3)
    body = "\n".join(lines)
    ax.text(x + w / 2, y + h - 0.48, body, ha="center", va="top",
            fontsize=7.4, color="#F4F4F4", family="DejaVu Sans", zorder=3,
            linespacing=1.35)


def arrow(ax, x1, y1, x2, y2, label, color=TEAL):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.6,
                        connectionstyle="arc3,rad=0"),
        zorder=4,
    )
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    ax.text(mx, my + 0.12, label, ha="center", va="bottom", fontsize=6.8,
            color=color, fontweight="bold", zorder=5,
            bbox=dict(boxstyle="round,pad=0.15", fc=PAPER, ec=color, lw=0.6))


def main():
    fig, ax = plt.subplots(figsize=(13.2, 7.6), dpi=160)
    fig.patch.set_facecolor(BG)
    ax.set_xlim(0, 13.2)
    ax.set_ylim(0, 7.6)
    ax.axis("off")

    ax.text(6.6, 7.35, "M2-Shop  —  Architecture HLD  ·  Observabilité sécurisée",
            ha="center", va="center", fontsize=13, fontweight="bold", color=NAVY)
    ax.text(6.6, 6.98, "Aucun réseau privé commun Prod / Admin  ·  4 flux FORWARD uniquement",
            ha="center", va="center", fontsize=8, color=TEAL, style="italic")

    # Host SRE
    box(ax, 3.6, 5.85, 6.0, 0.95, "Hôte SRE  (Windows)",
        ["vagrant ssh  ·  NAT eth0  ·  Grafana https://127.0.0.1:3443  →  :3000"],
        HOST)

    # Zone bands
    ax.add_patch(Rectangle((0.25, 0.35), 4.05, 5.25, facecolor="#E8F1F6",
                           edgecolor=PROD, lw=1.0, linestyle="--", zorder=0))
    ax.add_patch(Rectangle((4.55, 0.35), 4.1, 5.25, facecolor="#F6EFE6",
                           edgecolor=FW, lw=1.0, linestyle="--", zorder=0))
    ax.add_patch(Rectangle((8.9, 0.35), 4.05, 5.25, facecolor="#EAF3EA",
                           edgecolor=ADMIN, lw=1.0, linestyle="--", zorder=0))

    ax.text(2.28, 5.4, "DMZ PRODUCTION", ha="center", fontsize=8,
            fontweight="bold", color=PROD)
    ax.text(6.6, 5.4, "INTER-ZONES", ha="center", fontsize=8,
            fontweight="bold", color=FW)
    ax.text(10.92, 5.4, "DMZ ADMINISTRATION", ha="center", fontsize=8,
            fontweight="bold", color=ADMIN)

    box(ax, 0.45, 2.15, 3.65, 3.05, "web-prod   10.0.20.20",
        [
            "eth1  net-prod",
            "Nginx  80 → 443",
            "Node Exporter  :9100  TLS 1.3",
            "Zabbix Agent2  push PSK",
            "Promtail  → Loki",
            "healer  :9095",
        ], PROD)

    box(ax, 4.75, 2.15, 3.7, 3.05, "fw-router",
        [
            "eth1  10.0.20.1   net-prod",
            "eth2  10.0.10.1   net-admin",
            "ip_forward = 1",
            "nftables  policy DROP",
            "FORWARD : 4 règles",
            "pas de LAN commun",
        ], FW)

    box(ax, 9.1, 2.15, 3.65, 3.05, "supervision   10.0.10.5",
        [
            "eth1  net-admin",
            "Prometheus  :9090",
            "Alertmanager  :9093",
            "Zabbix Server  :10051",
            "Loki  :3100",
            "Grafana  :3000 HTTPS",
        ], ADMIN)

    # FORWARD arrows
    arrow(ax, 9.1, 4.55, 4.1, 4.55, "①  9100  PULL  TLS")
    arrow(ax, 4.1, 3.95, 9.1, 3.95, "②  10051  PUSH  PSK")
    arrow(ax, 4.1, 3.35, 9.1, 3.35, "③  3100  logs")
    arrow(ax, 9.1, 2.75, 4.1, 2.75, "④  9095  heal  HTTP")

    # Public + SRE notes
    ax.add_patch(FancyBboxPatch((0.45, 0.5), 3.65, 1.45, boxstyle="round,pad=0.02,rounding_size=0.06",
                                facecolor=PAPER, edgecolor=PROD, lw=1.0, zorder=2))
    ax.text(2.28, 1.75, "Plan hôte (hors FORWARD)", ha="center", fontsize=7.5,
            fontweight="bold", color=PROD)
    ax.text(2.28, 1.15, "Internet → Nginx 80/443\nSSH Vagrant via NAT eth0\nDNS / mises à jour",
            ha="center", va="center", fontsize=7, color=NAVY)

    ax.add_patch(FancyBboxPatch((4.75, 0.5), 3.7, 1.45, boxstyle="round,pad=0.02,rounding_size=0.06",
                                facecolor=PAPER, edgecolor=FW, lw=1.0, zorder=2))
    ax.text(6.6, 1.75, "Routes statiques", ha="center", fontsize=7.5,
            fontweight="bold", color=FW)
    ax.text(6.6, 1.15, "Prod : 10.0.10.0/24 via .20.1\nAdmin : 10.0.20.0/24 via .10.1\nSinon NAT = Zero-Trust inopérant",
            ha="center", va="center", fontsize=7, color=NAVY)

    ax.add_patch(FancyBboxPatch((9.1, 0.5), 3.65, 1.45, boxstyle="round,pad=0.02,rounding_size=0.06",
                                facecolor=PAPER, edgecolor=ADMIN, lw=1.0, zorder=2))
    ax.text(10.92, 1.75, "Défense en profondeur", ha="center", fontsize=7.5,
            fontweight="bold", color=ADMIN)
    ax.text(10.92, 1.15, "10051 / 3100 : saddr 10.0.20.20\n9100 / 9095 : daddr 10.0.20.20\nGrafana : port-forward hôte",
            ha="center", va="center", fontsize=7, color=NAVY)

    fig.tight_layout(pad=0.3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(OUT)


if __name__ == "__main__":
    main()
