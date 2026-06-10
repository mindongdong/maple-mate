# ADR-0003 — CD 게이팅: Render autoDeploy + GitHub branch protection

- **상태:** 채택 (Accepted)
- **일자:** 2026-06-09
- **관련 문서:** [deploy-plan.md](../deploy-plan.md) §1(배포 아키텍처), [cicd-work-order.md](../cicd-work-order.md)(구현), [../render.yaml](../render.yaml), [../Dockerfile](../Dockerfile)
- **이력:** CI/CD 구축 그릴링 세션(2026-06-09)에서 D1 결정으로 확정.

## 맥락 (Context)

Render 가 GitHub App 웹훅으로 **기본 브랜치(main) 변경을 자동 감지 → Docker 빌드 → `alembic upgrade head` → 기동**한다(`render.yaml autoDeploy:true`, `Dockerfile` CMD). 즉 "배포(CD)" 자체는 이미 동작한다.

핵심 위험은 **마이그레이션이 매 배포 자동 실행**된다는 점이다 — 깨진 마이그레이션이 main 에 들어가면 곧장 prod 기동을 막는다. 그런데 배포 *전* 게이트가 없었다: main 직접 푸시가 가능했고(branch protection 없음), 머지 전 CI(린트·테스트·마이그레이션 검증)도 없었다. 운영자 = 개발자 = 단일 1인이다.

## 결정 (Decision)

**A안 — Render 네이티브 autoDeploy 유지 + GitHub branch protection 으로 main 갱신을 게이팅한다.**

1. `render.yaml` 은 손대지 않는다(`autoDeploy:true` 유지).
2. GitHub main 에 branch protection: **PR 필수** + **required status check = CI**(lint·test·migrations 3잡 그린 필수).
3. **admin 우회 허용** — "Do not allow bypassing the above settings" 를 켜지 *않는다*. 1인 개발 현실상 긴급 핫픽스의 main 직푸시 여지를 남긴다.

결과적으로 main 은 평시 **항상 CI-그린 PR 로만** 갱신되고, Render 는 이미 검증된 main 커밋만 자동 배포한다. 별도 배포 워크플로·시크릿이 필요 없다.

## 검토한 대안 (Alternatives Considered)

- **B안. autoDeploy:false + GHA Deploy Hook** — *기각.* `push:[main]` 워크플로가 CI 통과 후 `curl <RENDER_DEPLOY_HOOK_URL>` 로 배포를 트리거. **배포 시점 하드 게이트**라 더 엄격하나, `RENDER_DEPLOY_HOOK_URL` 시크릿 관리 + `render.yaml` 변경 + `deploy.yml` 유지 부담이 늘고, branch protection 이면 main 이 이미 그린이라 A 로 충분. 1인·취미 봇 규모에 과함.
- **A안 + 우회 금지(엄격)** — *기각.* 본인도 모든 main 변경을 PR+그린 CI 로만. 최대 안전이나 핫픽스조차 PR 을 강제 → 1인 개발에 마찰. CI 가 안전망이지 족쇄일 필요는 없다.

## 결과 (Consequences)

**긍정**
- 추가 시크릿·배포 워크플로 없음, `render.yaml` 무변경 → native 단순.
- main 은 CI-그린 상태로만 갱신 → Render 가 보는 푸시는 이미 lint·test·**마이그레이션 검증**을 통과. 깨진 마이그레이션의 prod 직격을 평시 차단.

**부담 / 잔류**
- **게이트가 GitHub 설정에 의존** — `render.yaml`·워크플로 파일만 봐서는 "prod 배포가 어떻게 보호되는지" 안 보인다(설정은 레포 밖). *이 ADR 이 존재하는 핵심 이유.*
- **admin 우회 허용** — 본인이 main 직푸시하면 CI 우회 + Render 직배포 가능(자기규율 의존). 강화하려면 "우회 금지" 토글 또는 B안 전환.
- **CI migrations 잡은 빈 DB 기준** — "마이그레이션이 빈 DB→head 로 적용되는가"는 검증하나, *현재 prod 데이터 상태와의 충돌*은 못 잡는다(A·B 공통 한계).

## 참조

- 구현: `.github/workflows/ci.yml`(migrations 잡), [cicd-work-order.md](../cicd-work-order.md) §2·§6(완료 기록)
- 운영자 설정: branch protection 활성화는 [cicd-work-order.md](../cicd-work-order.md) §4
