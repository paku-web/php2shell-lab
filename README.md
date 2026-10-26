# PHP2Shell Lab

Lab terkawal untuk menyelidik mekanik **PHP2Shell** (CVE-2026-109618 & CVE-2026-109619) dalam persekitaran Alpine PHP 8.4.26.

> ⚠️ **Amaran**: Repo ini untuk tujuan pendidikan sahaja. Semua eksperimen dijalankan pada lab tempatan (Docker, localhost). Jangan guna terhadap sistem tanpa kebenaran bertulis.

---

## Author

**Paku** ([@SymphoeniX](https://github.com/SymphoeniX))

---

## 🎯 Matlamat

1. Fahami mekanik PHP2Shell (OOM bailout → heap leak → code leak → callback)
2. Bina lab Alpine PHP 8.4.26 yang serasi dengan offset calibration
3. Tulis PoC sendiri untuk eksperimen
4. Uji mitigasi (patch PHP, memory limit, worker config)

---

## 🚀 Quick Start

```bash
git clone https://github.com/SymphoeniX/php2shell-lab.git
cd php2shell-lab

# Setup lab
./scripts/setup-lab.sh

# Run PoC
./scripts/run-poc.sh 5

# Cleanup
./scripts/teardown-lab.sh
