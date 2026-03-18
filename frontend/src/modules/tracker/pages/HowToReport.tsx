import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';

export default function HowToReport(): JSX.Element {
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" className="gap-1" onClick={() => navigate('/tracker/my-report')}>
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <h1 className="text-2xl font-semibold">How to Report</h1>
      </div>

      <Card>
        <CardContent className="pt-6 prose prose-sm dark:prose-invert max-w-none">
          <section className="mb-6">
            <h2 className="text-lg font-semibold mt-0">1. Contracts</h2>
            <p>
              A contract represents what we call internally a <strong>project</strong>, usually where
              people with an engineering, design, research, science, data, or project management role
              will report most of their time. There may be exceptions, depending on unique project
              requirements or certain business times. This applies regardless of whether a task exceeds
              its expected duration if it necessitates learning something new, onboarding a new team
              member to a project or any other particular scenario. The key is that our efforts are
              enhancing the project's value directly.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold">2. Marketing & Business Development (MKT & BD)</h2>
            <p>
              All marketing and business development tasks. This can be anything from generating new
              project leads, writing proposals for potential clients, attending new scope of work
              meetings, or participating in conferences and networking events.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold">3. Communications (Comms)</h2>
            <p>
              Activities related to creating and managing both internal and external communication.
              This includes writing and editing blog posts, creating and scheduling social media posts,
              updating our websites, and any other content creation for Vizzuality's communication channels.
            </p>
            <p className="text-muted-foreground italic">
              Note: Some communication activities are included in the clients' contracts. In that case,
              those tasks should be reported under the respective projects.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold">4. Operations</h2>
            <p>
              All activities essential to the functioning of Vizzuality that cannot be directly linked
              to a specific project, MKT&BD, Comms or training. This includes functional area meetings,
              all-hands meetings, and hiring activities. Cross-functional strategic meetings and
              functional area leadership are considered operational tasks. Lightning talks that deal
              with efficiency or present new processes and workflows should also be tagged as operations.
              Technical lightning talks about new technologies or for sharing knowledge on a certain
              topic should be reported under mentoring (see point 6).
            </p>
            <p className="text-muted-foreground italic">
              Note: It is expected that operations take up 5-10% of junior and mid-level profiles
              reporting, whereas it can be more significant in senior positions. Ideally, operations
              should not exceed 20% of a person's time (except for specific profiles). During
              overcapacity periods, idle time should be monitored, and for that reason, tagged
              independently from operations (see point 8).
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold">5. Growth Plan</h2>
            <p>
              This category is reserved for <strong>learning activities</strong> aimed at professional
              development. It may also include activities like attending a lightning talk about a
              specific technology, or learning a new technique. Time dedicated to attending a course
              should be registered here.
            </p>
            <p>
              We believe that learning and the growth plan are crucial at our company; hence, we think
              that these activities cannot be reactive and driven by a lack of basic knowledge to
              address project problems. On the other hand, if a project brings some technical
              challenges, new technologies, or techniques, these have been considered when writing
              the proposal, so this time must be reported to that specific contract.
            </p>
            <p className="text-muted-foreground italic">
              Note: New staff undergoing general company onboarding should report their onboarding time
              in this category. Please note that onboarding a new team member to a project is project
              related and should be reported under its respective contract. Exceptions can be made for
              project onboardings that are part of the general company onboarding. However, all these
              exceptional and specific cases should have a team agreement.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold">6. Mentoring</h2>
            <p>
              Mentoring is the time we spend doing company general onboarding, helping others with
              their growth plan, or solving doubts or advice on projects. These must be reported to
              mentoring, not to operations. Teaching other team members about specific technical issues
              or preparing and giving a talk internally should be reported under mentoring.
            </p>
            <p className="text-muted-foreground italic">
              Note: To ensure clarity, if your contributions are enhancing the project in a significant
              way, they should be logged under the project's contract. For instance, if you're coding,
              designing, or processing data to introduce a discernible feature or benefit to the project,
              such activities must be reported to the project's contract.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold">7. Vacation / Absence</h2>
            <p>
              Vacation time or justified absences, such as parental or medical leaves. National or
              regional bank holidays should <strong>NOT</strong> be reported. Absences must also be
              logged in Bamboo.
            </p>
          </section>

          <section className="mb-6">
            <h2 className="text-lg font-semibold">8. Idle</h2>
            <p>
              Time that is not actively engaged in productive work. This time cannot be associated
              with a specific project, nor directly related to company activities or operations. During
              regular operation times, we aim to keep this at 0%. For that, it is key to turn any idle
              time into productive time. This could mean going the extra mile on ongoing projects,
              helping other team members or other FAs, or working on internal projects.
            </p>
            <p className="text-muted-foreground italic">
              Note: If you find yourself with idle time, talk to your FA to identify needs and
              initiatives where you can contribute. Be proactive and suggest some ideas too. For FAs,
              as a rule of thumb, project work should be assigned to junior and mid profiles, freeing
              senior members to more strategic tasks focusing on efficiency and innovation. Balancing
              the workload across all members of the same FA is also something to consider.
            </p>
          </section>

          <div className="mt-6 rounded-md border border-border bg-muted/50 p-4">
            <p className="text-sm text-muted-foreground m-0">
              If you have any questions about reporting, ask the team involved (e.g. doubts on
              operations reporting ask Laura/David; doubts on projects ask PMs; doubts on marketing
              ask BD; etc).
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
