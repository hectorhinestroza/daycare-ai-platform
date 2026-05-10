// /privacy — placeholder Privacy Policy page.
//
// IMPORTANT: This content is a STARTING POINT generated from the
// requirements in `docs/legal_prd_v1.md §12`. It has NOT been reviewed
// by a lawyer. Replace before the first parent receives a bootstrap URL.

const SECTIONS = [
  {
    heading: 'What information we collect',
    body: (
      <>
        <p>
          Through your daycare center, we collect information about your child
          to deliver daily reports and operational services:
        </p>
        <ul className="list-disc pl-6 mt-2 space-y-1">
          <li>Child's first name, last initial, date of birth, and classroom assignment</li>
          <li>Allergies and medical notes provided by you on the consent form</li>
          <li>Voice recordings from teachers describing your child's day</li>
          <li>Text descriptions of activities (food, naps, potty, observations, incidents, medication)</li>
          <li>Photos taken by teachers during the day</li>
          <li>Your name, email, phone, and pickup permission settings as the parent contact</li>
        </ul>
      </>
    ),
  },
  {
    heading: 'How we use this information',
    body: (
      <ul className="list-disc pl-6 space-y-1">
        <li>Generating daily reports for you to read in this portal</li>
        <li>Sharing real-time updates from the classroom</li>
        <li>Billing and invoicing for childcare services</li>
        <li>Maintaining a compliance audit trail required by childcare regulations</li>
      </ul>
    ),
  },
  {
    heading: 'Who we share information with',
    body: (
      <ul className="list-disc pl-6 space-y-1">
        <li><b>OpenAI</b> — voice transcription and event extraction. We have a Data Processing Agreement; OpenAI does not train models on your data.</li>
        <li><b>Twilio</b> — WhatsApp message delivery. Voice and photo files are deleted from Twilio servers immediately after we receive them.</li>
        <li><b>AWS S3</b> — photo storage. Photos are deleted after 90 days.</li>
        <li><b>Railway / Vercel</b> — infrastructure hosting.</li>
        <li><b>Sentry</b> — error monitoring, with PII redacted before transmission.</li>
        <li>We do <b>not</b> sell or share data with advertisers or third-party marketers.</li>
      </ul>
    ),
  },
  {
    heading: 'Your rights as a parent',
    body: (
      <ul className="list-disc pl-6 space-y-1">
        <li><b>Review</b> all information collected about your child</li>
        <li><b>Correct</b> inaccurate information</li>
        <li><b>Delete</b> your child's information (COPPA deletion request — see contact below)</li>
        <li><b>Withdraw consent</b> at any time, which stops further collection</li>
        <li>To exercise any right, contact your daycare director, or email us directly using the address below</li>
      </ul>
    ),
  },
  {
    heading: 'How long we keep information',
    body: (
      <ul className="list-disc pl-6 space-y-1">
        <li>Voice recordings — deleted immediately after transcription (zero retention)</li>
        <li>Photos — deleted 90 days after capture</li>
        <li>Event records, daily narratives, billing records — retained for the duration of enrollment plus 7 years for compliance/audit purposes</li>
        <li>Consent records — retained indefinitely as required by COPPA</li>
      </ul>
    ),
  },
  {
    heading: 'COPPA deletion requests',
    body: (
      <p>
        To request deletion of your child's information, contact us at the email
        below. We will confirm receipt within 5 business days and complete
        deletion within 30 days, subject to legal-hold exceptions for billing
        and compliance records.
      </p>
    ),
  },
  {
    heading: 'Contact',
    body: (
      <p>
        Questions or requests: <a className="underline" href="mailto:privacy@raina-pilot.com">privacy@raina-pilot.com</a>.
        Mailing address available on request.
      </p>
    ),
  },
];

export default function PrivacyPolicy() {
  return (
    <div className="min-h-screen bg-surface py-12 px-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="font-headline text-3xl font-semibold text-on-surface mb-2">
          Privacy Policy
        </h1>
        <p className="text-sm text-on-surface-variant mb-8">
          Last updated: May 2026 — <span className="italic">draft pending legal review</span>
        </p>

        <div className="space-y-8 text-on-surface leading-relaxed">
          {SECTIONS.map((s) => (
            <section key={s.heading}>
              <h2 className="font-headline text-xl font-semibold mb-3">{s.heading}</h2>
              <div className="text-on-surface-variant">{s.body}</div>
            </section>
          ))}
        </div>

        <footer className="mt-12 pt-6 border-t border-outline-variant/20 text-xs text-on-surface-variant/70">
          This policy is provided for the pilot launch and complies with the
          Children's Online Privacy Protection Act (COPPA) as required by
          the FTC's amended rule effective April 22, 2026. It will be
          reviewed annually and after any material change in data handling.
        </footer>
      </div>
    </div>
  );
}
