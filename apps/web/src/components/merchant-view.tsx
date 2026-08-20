"use client";
/* eslint-disable no-unused-vars -- the base ESLint preset does not understand TypeScript callback parameter names. */

import type { CurrencyFlow, PeoplePlace } from "../lib/api";
import { formatMoney } from "../lib/format";
import { LensSummary } from "./lens-summary";

type ActivityPatch = { counterparty?: string; merchant?: string; offset?: string; query?: string; selected?: string; state?: string; unresolvedGroup?: string };

const sections = [
  { kind: "person", title: "People and transfers" },
  { kind: "place", title: "Places and merchants" },
  { kind: "unresolved", title: "Needs review" },
] as const;

function activityPatch(group: PeoplePlace): ActivityPatch {
  if (group.kind === "person") return { counterparty: group.label, merchant: undefined, offset: undefined, query: undefined, selected: undefined, state: undefined, unresolvedGroup: undefined };
  if (group.kind === "place") return { counterparty: undefined, merchant: group.label, offset: undefined, query: undefined, selected: undefined, state: undefined, unresolvedGroup: undefined };
  return { counterparty: undefined, merchant: undefined, offset: undefined, query: undefined, selected: undefined, state: undefined, unresolvedGroup: group.key.replace("unresolved:", "") };
}

function GroupCard({ group, onShowActivity }: Readonly<{ group: PeoplePlace; onShowActivity: (patch: ActivityPatch) => void }>) {
  const needsReview = group.status === "unresolved";
  return (
    <article className="candidate-card people-place-card" aria-label={group.label}>
      <div className="candidate-heading">
        <div>
          <h3>{group.label}</h3>
          <span className={`status-badge ${needsReview ? "unresolved" : "confirmed"}`}>{needsReview ? "Needs review" : "Confirmed"}</span>
        </div>
      </div>
      <p className="group-meta">{group.transactionCount} {group.transactionCount === 1 ? "transaction" : "transactions"} · Last activity {group.lastActivityDate}</p>
      <div className="group-flows">
        {group.flows.map((flow) => (
          <dl key={flow.currency} className="currency-flow" aria-label={`${group.label} ${flow.currency} flow`}>
            <dt>{flow.currency}</dt>
            <dd><span>Sent</span>{formatMoney(flow.sent_minor, flow.currency)}</dd>
            <dd><span>Received</span>{formatMoney(flow.received_minor, flow.currency)}</dd>
            <dd><span>Net flow</span>{formatMoney(flow.net_minor, flow.currency)}</dd>
          </dl>
        ))}
      </div>
      <button className="button secondary" type="button" onClick={() => onShowActivity(activityPatch(group))}>
        {needsReview ? "Review in activity" : "Show activity"}
      </button>
    </article>
  );
}

export function MerchantView({ scope, flows, peoplePlaces, onShowActivity, loadError }: Readonly<{ scope: string; flows: readonly CurrencyFlow[]; peoplePlaces: readonly PeoplePlace[]; onShowActivity: (patch: ActivityPatch) => void; loadError?: string }>) {
  return (
    <section className="record-view" aria-labelledby="people-title">
      <p className="eyebrow">People and places</p>
      <h1 id="people-title">The names behind your activity</h1>
      <p className="scope-note">Scope: {scope}</p>
      <p className="intro">People and places in this period, grouped from your trusted activity.</p>
      {flows.length > 0 && <LensSummary flows={flows} />}
      {loadError ? <p className="empty-note" role="status">{loadError}</p> : peoplePlaces.length ? sections.map((section) => {
        const groups = peoplePlaces.filter((group) => group.kind === section.kind);
        return groups.length ? (
          <section className="group-section" aria-labelledby={`group-${section.kind}`} key={section.kind}>
            <h2 id={`group-${section.kind}`}>{section.title}</h2>
            <div className="candidate-grid">{groups.map((group) => <GroupCard key={group.key} group={group} onShowActivity={onShowActivity} />)}</div>
          </section>
        ) : null;
      }) : <p className="empty-note">There are no people or places in this period.</p>}
    </section>
  );
}
