/**
 * 튜토리얼 스크린 12개의 단일 소스 (docs/tutorial-work-order.md §3 커리큘럼).
 *
 * - 챕터 8개 · 스크린 12개. `chapter`가 같은 연속 스크린이 프로그래스바 한 칸.
 * - media.type 'video' 스크린은 PR2에서 운영자 녹화 mp4 로 교체된다.
 *   PR1 은 `src: null`(폴백 렌더). PR2 = src/poster 만 채우면 끝.
 * - ⚠️ 드리프트 가드(scripts/check-command-drift.mjs · tests/test_website_command_drift.py)가
 *   이 파일을 정규식으로 읽는다. 명령 객체는 반드시
 *   { name: <'명령'>, visibility?: <'public'|'private'>, label?: <'표시문구'> }
 *   리터럴 형태·이 키 순서로 쓰고(따옴표는 실제 값에만), name: 키를 다른 용도로 쓰지 말 것.
 *   label 은 칩 표시 전용(검증은 name 기준). broadcasts 는 명령이 아닌 자동 발송물 이름.
 * - visibility 정본 = 작업지시서 §3.1 (봇 코드 ephemeral 실태). 라벨 두 값:
 *   public="다같이 봐요" / private="나만 봐요".
 */
import type * as React from 'react'
import { CommandSequenceDemo } from '@/components/CommandSequenceDemo'
import { DiscordDemo } from '@/components/DiscordDemo'
import {
  AlertsDemo,
  FinishPanel,
  KeyIssueDemo,
  KeyRegisterDemo,
  RegisterDemo,
  ShotCollage,
  SlashDemo,
  TargetDemo,
} from '@/components/TutorialDemos'

export type Visibility = 'public' | 'private'

export type TutorialCommand = {
  name: string
  visibility?: Visibility
  /** 칩에 name 대신 보여줄 문구(예: 토글 명령의 "켜기/끄기" 병기). */
  label?: string
}

export type TutorialMedia =
  | {
      type: 'video'
      /** PR2 에서 채움 — null 이면 fallback 렌더. */
      src: string | null
      poster?: string
      fallback: React.ReactNode
    }
  | { type: 'image'; node: React.ReactNode }
  | { type: 'anim'; node: React.ReactNode }

export type TutorialStep = {
  chapter: string
  title: string
  sub?: React.ReactNode
  media?: TutorialMedia
  /** 'doors' = 명령 칩 + 공개/본인만 라벨 목록 · 'summary' = 공개/비공개 2버킷 총정리 */
  layout?: 'doors' | 'summary'
  commands: TutorialCommand[]
  /** summary 전용 — 명령이 아닌 자동 발송물(채널 공개) 이름 목록. */
  broadcasts?: string[]
}

export const TUTORIAL_STEPS: TutorialStep[] = [
  // ---- 1. 인트로 ----
  {
    chapter: '인트로',
    title: '캐릭터 한 번 등록하면, 계속 함께하는 봇',
    sub: '메이트가 해주는 일을 5분 만에 따라가 봐요.',
    media: { type: 'anim', node: <DiscordDemo /> },
    commands: [],
  },
  // ---- 2. 초대하기 ---- 🎬① (PR2: /tutorial/invite.mp4)
  {
    chapter: '초대하기',
    title: '먼저, 서버에 메이트를 초대하세요',
    sub: '서버만 고르고 승인하면 끝, 권한은 봇이 메시지를 보내기 위한 최소한의 권한만 설정했어요.',
    media: {
      type: 'video',
      src: null, // PR2: '/tutorial/invite.mp4' + poster '/tutorial/invite-poster.png'
      fallback: (
        <ShotCollage
          shots={[
            { src: '/shots/invite-1.png', alt: '디스코드 봇 초대 — 서버 선택 화면' },
            { src: '/shots/invite-2.png', alt: '디스코드 봇 초대 — 권한 확인 화면' },
          ]}
        />
      ),
    },
    commands: [],
  },
  // ---- 3. 명령어 기초 ---- 🎬② (PR2: /tutorial/slash-basics.mp4)
  {
    chapter: '명령어 기초',
    title: '채팅창에 / 만 입력하면 시작돼요',
    sub: '모든 명령이 이 패턴이에요. 휴대폰에서도 똑같이 / 를 입력하면 돼요.',
    media: {
      type: 'video',
      src: null, // PR2: '/tutorial/slash-basics.mp4' + poster '/tutorial/slash-basics-poster.png'
      fallback: <SlashDemo />,
    },
    commands: [{ name: '가이드' }],
  },
  // ---- 4. 등록 없이 되는 것 ----
  {
    chapter: '등록 없이 되는 것',
    title: '초대 직후, 등록 없이 바로 되는 것',
    sub: '세 가지 알림은 등록 없이 지금 바로 켤 수 있어요.',
    media: { type: 'image', node: <AlertsDemo /> },
    layout: 'doors',
    commands: [
      { name: '경험치알림' },
      { name: '공지알림' },
      { name: '썬데이알림' },
    ],
  },
  // ---- 5. 캐릭터 등록 ---- 🎬③ (PR2: /tutorial/register.mp4)
  {
    chapter: '캐릭터 등록',
    title: '닉네임만 있으면 캐릭터 등록 끝',
    sub: '/캐릭터등록 — 여러 캐릭터를 등록해도 돼요.',
    media: {
      type: 'video',
      src: null, // PR2: '/tutorial/register.mp4' + poster '/tutorial/register-poster.png'
      fallback: <RegisterDemo />,
    },
    commands: [{ name: '캐릭터등록', visibility: 'private' }],
  },
  // ---- 5-2. 열리는 문(캐릭터) ---- ✨ 명령 시퀀스 애니(CommandSequenceDemo S6)
  {
    chapter: '캐릭터 등록',
    title: '캐릭터 등록으로 열리는 명령들',
    sub: '전부 서버에 공개 — 친구들과 비교하고 자랑하는 용도예요.',
    media: { type: 'anim', node: <CommandSequenceDemo script="S6" /> },
    layout: 'doors',
    commands: [
      { name: '스펙', visibility: 'public' },
      { name: '아이템', visibility: 'public' },
      { name: '유니온', visibility: 'public' },
      { name: '경험치', visibility: 'public' },
      { name: '내캐릭터', visibility: 'public' },
    ],
  },
  // ---- 6. API 키 발급 ---- 🎬④ (PR2: /tutorial/key-issue.mp4)
  {
    chapter: 'API 키',
    title: '스타포스·잠재·스케줄러엔 넥슨 API 키가 필요해요',
    sub: (
      <>
        <a href="https://openapi.nexon.com" target="_blank" rel="noreferrer">
          openapi.nexon.com
        </a>{' '}
        에서 바로 발급 가능해요. 애플리케이션 등록만 하고 키 값 복사해서 보관해주세요.
      </>
    ),
    media: {
      type: 'video',
      src: null, // PR2: '/tutorial/key-issue.mp4' + poster '/tutorial/key-issue-poster.png'
      fallback: <KeyIssueDemo />,
    },
    commands: [],
  },
  // ---- 6-2. /키등록 ---- 🎬⑤ (PR2: /tutorial/key-register.mp4)
  {
    chapter: 'API 키',
    title: '/키등록 으로 붙여넣으면 끝',
    sub: '입력은 본인에게만 보여요. 키는 암호화해 보관해요.',
    media: {
      type: 'video',
      src: null, // PR2: '/tutorial/key-register.mp4' + poster '/tutorial/key-register-poster.png'
      fallback: <KeyRegisterDemo />,
    },
    commands: [{ name: '키등록', visibility: 'private' }],
  },
  // ---- 6-3. 열리는 문(API 키) ---- ✨ 명령 시퀀스 애니(CommandSequenceDemo S9)
  {
    chapter: 'API 키',
    title: 'API 키로 열리는 명령들',
    sub: '스타포스·잠재는 서버에 공개, 스케줄러 숙제는 나만 봐요.',
    media: { type: 'anim', node: <CommandSequenceDemo script="S9" /> },
    layout: 'doors',
    commands: [
      { name: '스타포스', visibility: 'public' },
      { name: '잠재', visibility: 'public' },
      { name: '스케줄러', visibility: 'private' },
    ],
  },
  // ---- 7. 사용 기조: 대상 지정 ----
  {
    chapter: '사용 기조',
    title: '대상을 안 적으면, 본인 포함 랜덤 최대 10명과 비교해요',
    sub: '등록자가 많아도 공평하게 — 명령을 실행한 본인은 항상 들어가고, 나머지는 등록자 중 랜덤으로 채워요. 대상을 지정하면 그 사람들만 비교해요 (최대 5명, /스펙은 지정 필수). /경험치는 레벨 Top 10 리더보드예요.',
    media: { type: 'anim', node: <TargetDemo /> },
    commands: [{ name: '유니온', visibility: 'public' }],
  },
  // ---- 7-2. 사용 기조: 공개/비공개 총정리 ----
  {
    chapter: '사용 기조',
    title: '어디까지 보일까? 한눈 정리',
    sub: '등록·키 입력·숙제·알림 설정은 나만, 비교·리더보드·알림 발송은 다같이.',
    layout: 'summary',
    commands: [
      { name: '스펙', visibility: 'public' },
      { name: '아이템', visibility: 'public' },
      { name: '유니온', visibility: 'public' },
      { name: '경험치', visibility: 'public' },
      { name: '내캐릭터', visibility: 'public' },
      { name: '스타포스', visibility: 'public' },
      { name: '잠재', visibility: 'public' },
      { name: '캐릭터등록', visibility: 'private' },
      { name: '키등록', visibility: 'private' },
      { name: '캐릭터목록', visibility: 'private' },
      { name: '대표지정', visibility: 'private' },
      { name: '스케줄러', visibility: 'private' },
      { name: '공지알림', visibility: 'private', label: '공지알림 켜기/끄기' },
      { name: '썬데이알림', visibility: 'private', label: '썬데이알림 켜기/끄기' },
      { name: '경험치알림', visibility: 'private', label: '경험치알림 켜기/끄기' },
    ],
    broadcasts: ['공지 알림', '썬데이 알림', '경험치 리더보드'],
  },
  // ---- 8. 완료 ----
  {
    chapter: '완료',
    title: '이제 다 봤어요 — 서버에서 만나요!',
    sub: '초대하고 /캐릭터등록 부터 시작해 보세요.',
    media: { type: 'anim', node: <FinishPanel /> },
    commands: [],
  },
]

/** 챕터 목록(등장 순서 유지) — 프로그래스바 세그먼트. */
export const TUTORIAL_CHAPTERS: string[] = TUTORIAL_STEPS.reduce<string[]>(
  (acc, s) => (acc[acc.length - 1] === s.chapter ? acc : [...acc, s.chapter]),
  [],
)
