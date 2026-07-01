/**
 * 3기둥 카드(비교·비서·함께) — 밴드 밖 쿨 베이스 섹션(D8).
 * 카드 상단 컬러 스트라이프(teal/orange/green), Lucide 아이콘(D13).
 */
import { Trophy, CalendarCheck, Users } from 'lucide-react'

export function Pillars() {
  return (
    <section className="mm-pillars">
      <div className="mm-pillars-inner">
        <header className="mm-pillars-header">
          <span className="mm-pillars-dot" />
          <div>
            <h2 className="mm-pillars-title">메이트가 하는 일</h2>
            <p className="mm-pillars-sub">
              캐릭터를 한 번 등록해두면, 친구들과 겨루고 성장하는 메이플의 재미가 더해집니다.
            </p>
          </div>
        </header>

        <div className="mm-pillar-grid">
          <article className="mm-pillar mm-pillar--teal">
            <span className="mm-pillar-icon mm-pillar-icon--teal">
              <Trophy size={20} strokeWidth={2} aria-hidden />
            </span>
            <h3 className="mm-pillar-name">같이 비교하기</h3>
            <p className="mm-pillar-desc">
              경험치 리더보드로 친구·길드원과 순위를 겨루고, 스타포스·잠재에 쓴
              메소와 운빨까지 재미로 비교해요.
            </p>
            <div className="mm-pillar-shot">
              <div className="mm-mini-bar"><span className="mm-mini-name" style={{ color: '#f0c040' }}>홍길동</span><span className="mm-mini-bg"><span className="mm-mini-fill" style={{ width: '92%', background: '#f0c040' }} /></span></div>
              <div className="mm-mini-bar"><span className="mm-mini-name" style={{ color: '#5ec8c8' }}>불꽃아크</span><span className="mm-mini-bg"><span className="mm-mini-fill" style={{ width: '80%' }} /></span></div>
              <div className="mm-mini-bar"><span className="mm-mini-name" style={{ color: '#9ab0c8' }}>바람궁수</span><span className="mm-mini-bg"><span className="mm-mini-fill" style={{ width: '71%', background: '#9ab0c8' }} /></span></div>
            </div>
          </article>

          <article className="mm-pillar mm-pillar--orange">
            <span className="mm-pillar-icon mm-pillar-icon--orange">
              <CalendarCheck size={20} strokeWidth={2} aria-hidden />
            </span>
            <h3 className="mm-pillar-name">숙제 DM 비서</h3>
            <p className="mm-pillar-desc">
              일일·주간·보스 숙제를 개인 DM으로 챙겨드려요. 원하는 묶음만 골라
              받고, 남은 숙제를 한눈에.
            </p>
            <div className="mm-pillar-shot">
              <div className="mm-mini-dm"><span className="mm-mini-dot" />에픽던전 ⬜ 미완료</div>
              <div className="mm-mini-dm"><span className="mm-mini-dot orange" />무릉도장 ✅ 완료</div>
              <div className="mm-mini-dm"><span className="mm-mini-dot" />주간 보스 5/8</div>
            </div>
          </article>

          <article className="mm-pillar mm-pillar--green">
            <span className="mm-pillar-icon mm-pillar-icon--green">
              <Users size={20} strokeWidth={2} aria-hidden />
            </span>
            <h3 className="mm-pillar-name">서버에서 함께</h3>
            <p className="mm-pillar-desc">
              캐릭터를 한 번 등록하면 친구·길드원과 나란히 묶여요. 썬데이·공지
              알림까지 곁에서 챙겨드립니다.
            </p>
            <div className="mm-pillar-shot">
              <div className="mm-mini-cells">
                <span className="mm-cell on" /><span className="mm-cell on" /><span className="mm-cell part" /><span className="mm-cell" /><span className="mm-cell" />
              </div>
              <div className="mm-mini-cells">
                <span className="mm-cell on" /><span className="mm-cell" /><span className="mm-cell on" /><span className="mm-cell on" /><span className="mm-cell" />
              </div>
            </div>
          </article>
        </div>
      </div>
    </section>
  )
}
