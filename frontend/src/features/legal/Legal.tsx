import { PageShell } from "../../app/layouts";
import type { ReactNode } from "react";

const Doc = ({ title, updated, children }: { title: string; updated: string; children: ReactNode }) => (
  <PageShell>
    <main className="container-page max-w-3xl py-14">
      <h1 className="font-display text-4xl font-bold">{title}</h1>
      <p className="mt-2 text-base text-ink-soft">Last updated {updated}. This is a prototype document and needs legal review before any real deployment.</p>
      <div className="mt-8 flex flex-col gap-5 [&_h2]:mt-4 [&_h2]:font-display [&_h2]:text-2xl [&_h2]:font-bold [&_ul]:list-disc [&_ul]:pl-6 [&_li]:mb-1">{children}</div>
    </main>
  </PageShell>
);

export function Terms() {
  return (
    <Doc title="Terms of Service" updated="8 October 2026">
      <p>These terms cover the Follow-up Coordinator prototype, built for the Acentra Hackathon. By using it you agree to them.</p>
      <h2>What this is</h2>
      <p>A tool that organizes and explains discharge instructions that you give it. It does not diagnose a condition, change or recommend medicine, or recommend treatment. It is not a medical device and has not been validated for clinical use.</p>
      <h2>Synthetic data only</h2>
      <p>Use only synthetic or public text. Do not enter real patient, provider or confidential information. Providers, phone numbers and summaries shown in the prototype are invented.</p>
      <h2>Your responsibilities</h2>
      <ul>
        <li>Check every task against your own discharge papers and ask your doctor about anything unclear.</li>
        <li>Do not rely on a reminder, translation or provider suggestion as medical advice.</li>
        <li>Keep your login private. A family member who operates your account does so only because you granted it.</li>
      </ul>
      <h2>Limits of the service</h2>
      <p>Extraction can misread a summary. Translations can contain mistakes. Provider matches come from a synthetic dataset and are never a guarantee of availability or suitability. Items the system is unsure about are held for a doctor reviewer, and the service is provided as is, without warranty.</p>
      <h2>Changes and contact</h2>
      <p>We may change these terms as the prototype changes. For questions, contact the project team through the hackathon organizers.</p>
    </Doc>
  );
}

export function Privacy() {
  return (
    <Doc title="Privacy Policy" updated="8 October 2026">
      <p>This policy describes how the Follow-up Coordinator prototype handles data. It follows the principles of the Digital Personal Data Protection Act 2023 and HIPAA style safeguards, but the prototype only runs on synthetic data.</p>
      <h2>What we store</h2>
      <ul>
        <li>Account details: name, login, language, and a hashed password.</li>
        <li>The text of the discharge summary you submit, the tasks extracted from it, and their source lines. These fields are encrypted at rest.</li>
        <li>Family links and the access level you chose for each person.</li>
        <li>An audit log of logins, views and actions. It never contains clinical text, passwords or full phone numbers.</li>
      </ul>
      <h2>What we do not store</h2>
      <ul>
        <li>Your location. GPS coordinates are used for a single provider search and are not saved.</li>
        <li>Uploaded files. Only the extracted text is kept, and the file itself is not written to disk.</li>
        <li>Call content. A callback records who, when and how long, nothing more.</li>
      </ul>
      <h2>Who can see it</h2>
      <p>You see everything. Family members see only the level you allow. A doctor reviewer sees only the items assigned to them. Hospital management sees queue status and reasons, never clinical text.</p>
      <h2>Third parties</h2>
      <p>Summary text, with no names or phone numbers, is sent to a language model provider to read and rewrite it, and approved task text may be sent to a text to speech provider when you press Listen. Both are used for synthetic data in this prototype.</p>
      <h2>Your rights</h2>
      <p>You can view your data and the log of who accessed it, change or remove family access at any time, and delete your account and data. The audit trail is append only and is kept.</p>
    </Doc>
  );
}
