import { useEffect, useMemo, useState } from "react";
import { API_BASE_URL } from "@/services/api";
import { getPlatformSummary } from "@/services/traction";
import { LandingHeader } from "@/components/layout/LandingHeader";
import { QmaLogo } from "@/components/QmaLogo";
import { AgentLoopReplay } from "./components/AgentLoopReplay";
import { ARC_CHAIN } from "@/config/network";
import "./HomePage.css";
import type { HomeProps } from "./Home.types";

function ArcLogoSvg() {
    return (
        <svg width="64" height="18" viewBox="0 0 500 171" fill="none" xmlns="http://www.w3.org/2000/svg" className="landing-partner-logo">
            <path d="M285.916 15.0039H261.887L213.618 161.833H227.74L240.387 122.819H307.416L320.063 161.833H334.185L285.916 15.0039ZM244.181 110.653L272.637 22.9749H275.166L303.622 110.653H244.181Z" fill="#FFFFFF" />
            <path d="M386.866 59.4688H398.881V71.2148H385.391C377.661 71.2148 371.479 73.3846 366.842 77.717C362.205 82.0532 359.886 88.8345 359.886 98.0638V161.829H347.239V59.8876H359.465V72.6831H361.994C363.96 68.0682 366.875 64.7121 370.741 62.6147C374.605 60.5174 379.98 59.4688 386.866 59.4688Z" fill="#FFFFFF" />
            <path d="M500 125.963C498.736 132.538 496.101 138.794 492.096 144.736C488.091 150.681 482.68 155.506 475.866 159.209C469.048 162.913 460.723 164.768 450.888 164.768C440.909 164.768 432.023 162.634 424.224 158.37C416.425 154.106 410.276 147.987 405.781 140.017C401.282 132.046 399.036 122.679 399.036 111.909V109.812C399.036 98.9043 401.282 89.5015 405.781 81.5998C410.276 73.701 416.425 67.6179 424.224 63.3509C432.023 59.087 440.909 56.9531 450.888 56.9531C460.723 56.9531 469.048 58.8083 475.866 62.5117C482.68 66.2188 488.019 71.0431 491.885 76.9848C495.748 82.9302 498.172 89.1868 499.157 95.7582L486.721 98.2752C486.016 92.8218 484.261 87.8237 481.451 83.2774C478.639 78.7355 474.706 75.0976 469.648 72.3705C464.589 69.6434 458.335 68.2803 450.888 68.2803C443.438 68.2803 436.766 69.9944 430.864 73.4192C424.962 76.8476 420.289 81.672 416.847 87.8923C413.402 94.1165 411.683 101.494 411.683 110.021V111.7C411.683 120.231 413.402 127.608 416.847 133.829C420.289 140.053 424.962 144.877 430.864 148.302C436.766 151.73 443.438 153.441 450.888 153.441C462.128 153.441 470.702 150.541 476.603 144.736C482.505 138.935 486.158 131.836 487.564 123.446L500 125.963Z" fill="#FFFFFF" />
            <path d="M0 171C1.39327 129.136 8.52567 90.067 20.4481 59.6871C35.5477 21.1972 57.4057 0 81.9919 0C106.578 0 128.433 21.1972 143.536 59.6871C151.391 79.7058 157.17 103.491 160.594 129.366C160.9 131.677 161.161 134.026 161.428 136.369C161.515 136.514 161.568 136.649 161.55 136.758C161.55 136.758 163.562 149.265 163.99 171H163.763C160.778 168.562 125.578 141.038 67.2282 149.007C68.1086 139.181 69.3194 129.62 70.8835 120.456C70.9634 119.987 71.0558 119.535 71.1373 119.07C94.0233 118.383 114.055 121.028 129.416 124.494C129.359 124.131 129.311 123.758 129.253 123.397C126.095 103.83 121.437 85.9161 115.43 70.6073C105.61 45.576 92.7953 30.0239 81.9919 30.0239C71.189 30.0239 58.3744 45.576 48.554 70.6073C46.1769 76.6621 44.0128 83.1192 42.0721 89.9301C39.3438 99.4735 37.0517 109.704 35.2212 120.455C32.5117 136.331 30.8189 153.358 30.1954 171H0Z" fill="#FFFFFF" />
        </svg>
    );
}

function CircleLogoSvg() {
    return (
        <svg width="70" height="18" viewBox="0 0 467 120" fill="none" xmlns="http://www.w3.org/2000/svg" className="landing-partner-logo">
            <g stroke="none" strokeWidth="1" fill="none" fillRule="evenodd">
                <path d="M107.046442,24.0367559 L107.229525,24.0429466 C108.021291,24.0965321 108.785773,24.4971117 109.267438,25.2105725 L109.373455,25.3807559 L111.982623,29.9284256 L112.332102,30.5461917 C117.168963,39.2171555 119.776543,49.0197553 119.897971,58.9870174 L119.902416,59.7166091 L119.894332,60.7082701 C119.366799,93.0439667 93.0875512,119.249482 60.6631206,119.770358 L59.6787013,119.77826 L58.9762553,119.774312 C46.1102123,119.62959 33.9190117,115.508787 23.6347741,107.826511 L23.0757143,107.403949 L19.4408052,104.624793 L19.3030045,104.512052 C18.1962664,103.544559 18.0831731,101.858417 19.0502381,100.753737 L19.1767532,100.618774 L43.8541299,76.0093063 L43.9927978,75.8804016 C44.7964918,75.1843923 45.9393733,75.0305621 46.8993418,75.4878995 L47.0770649,75.5808293 L49.7401039,77.1022972 L50.1542162,77.3323425 C52.9248531,78.8284963 56.0258304,79.6521728 59.180234,79.7308001 L59.6787013,79.7370128 L60.0239411,79.7340971 C70.8199092,79.5516296 79.567388,70.8277543 79.7503492,60.0609173 L79.7532727,59.7166091 L79.7448779,59.1448855 C79.7113161,58.0002547 79.5772237,56.8495552 79.3444638,55.7113648 L79.2198701,55.1433981 L78.7120779,52.9759118 L78.676336,52.7956548 C78.5497425,52.017442 78.7752794,51.2225375 79.2911087,50.6260867 L79.4260779,50.4812329 L85.478961,44.4442421 L85.6123886,44.3196079 C86.8840133,43.2083185 88.8698496,43.5481437 89.704516,45.0147039 L89.7894545,45.176132 L90.0800599,45.7915175 C91.5012494,48.8825857 92.4439866,52.1833146 92.8682319,55.5832873 L92.9461558,56.2645724 L93.0124073,56.9547684 C93.0721766,57.6452285 93.1120758,58.3363229 93.1282899,59.0266245 L93.1364675,59.7166091 L93.1319764,60.2675376 C92.8389036,78.2319958 78.2393668,92.790335 60.2256067,93.0797053 L59.6787013,93.0840953 L59.0029197,93.0772465 C55.4010312,93.0042435 51.8386831,92.3484338 48.4628725,91.1487871 L47.8321299,90.9174898 L37.7257403,100.996169 L38.3381548,101.316281 C44.6876007,104.575307 51.689098,106.320181 58.972944,106.426053 L59.6787013,106.431178 L60.4520829,106.424907 C85.6702071,106.015716 106.10728,85.6316832 106.5135,60.4802183 L106.519662,59.7166091 L106.5134,58.9521512 C106.43853,54.3820746 105.693035,49.8599971 104.317419,45.5411341 L104.06813,44.7811229 L104.052234,44.7965357 L103.792972,44.0486716 C102.642085,40.8178197 101.135283,37.7170244 99.2935489,34.8030449 L98.8625974,34.1339302 L98.763889,33.9717745 C98.210546,32.9879106 98.3218382,31.7653272 99.058219,30.912163 L99.1946494,30.7655632 L105.157896,24.8188476 C105.687325,24.2904073 106.369532,24.0367559 107.046442,24.0367559 Z M60.486,-0.124418434 C73.6667341,-0.124418434 86.1681463,4.00580251 96.6857079,11.8273531 L97.2472435,12.2498935 L100.8984,15.0290495 L101.036798,15.1417415 C102.148319,16.1088285 102.261524,17.7946067 101.290224,18.9000092 L101.163157,19.0350678 L76.3793739,43.6449761 L76.2400332,43.7738219 C75.4324516,44.469556 74.284245,44.6240508 73.3204124,44.1664446 L73.1419826,44.0734531 L70.4660348,42.5511045 L70.0502403,42.3211139 C67.2683256,40.8252892 64.1542863,40.0012671 60.986571,39.9226045 L60.486,39.9163889 L60.1392591,39.9193047 C49.2963521,40.101781 40.5108408,48.8260742 40.3270841,59.5924978 L40.3241478,59.9367926 L40.3325774,60.509347 C40.3662748,61.6553298 40.5008774,68.5055856 40.73414,63.9426509 L40.8589826,64.5100036 L41.3689826,66.6783706 L41.4048028,66.8585454 C41.5316631,67.6364293 41.3054764,68.4313319 40.7877826,69.0281077 L40.6523217,69.1730495 L34.5748957,75.2069577 L34.440928,75.3315948 C33.1641088,76.4429367 31.168904,76.1038673 30.3313293,74.636976 L30.2461043,74.4755082 L29.9558653,73.8632429 C28.5361874,70.7878474 27.5901773,67.5040619 27.158658,64.1310759 L27.0792261,63.4553247 L27.015587,62.8030862 L26.9652522,62.1505173 L26.9472359,61.8798568 L26.9315478,61.608866 L26.906286,61.0513777 L26.8891053,60.4939873 L26.8891053,60.4939873 L26.8827652,59.9367926 L26.8872757,59.385877 C27.1816142,41.4218333 41.8442054,26.8630752 59.9367039,26.5736965 L60.486,26.5693063 L61.1646538,26.5761591 C64.7818925,26.6492032 68.3600612,27.3053633 71.7505894,28.505051 L72.3840783,28.7363522 L82.5339652,18.6576733 L81.9188489,18.3375222 C75.5414058,15.0781068 68.5094794,13.333221 61.1947476,13.2273487 L60.486,13.2222238 L59.7092558,13.2284946 C34.3814789,13.637703 13.8551231,34.0225734 13.4471288,59.173209 L13.4409391,59.9367926 L13.4472316,60.7013729 C13.5224653,65.2721252 14.2715607,69.7938857 15.6531978,74.1127114 L15.9035739,74.8727192 L15.9182087,74.8581871 L16.1787082,75.6060842 C17.3351647,78.8372126 18.850105,81.9398941 20.6984132,84.8524962 L21.1308522,85.5212329 L21.2298033,85.683445 C21.7845136,86.6675905 21.6730556,87.8894805 20.9338666,88.7425668 L20.796913,88.8891595 L14.8086261,94.8349944 L14.6760819,94.958267 C13.4574755,96.0190347 11.5653419,95.7680108 10.6700311,94.4266069 L10.5747391,94.2730862 L7.95378261,89.7254164 L7.60278564,89.1077377 C2.74215799,80.4330406 0.123430396,70.6238367 0.00425789942,60.6495121 L0,59.9367926 L0.00811921685,58.9451317 C0.543297323,26.2828205 27.4672962,-0.124418434 60.486,-0.124418434 Z M178.288143,27.0013302 C186.797406,27.0013302 193.604816,29.6111442 200.36114,35.4610977 C200.914836,35.9507256 201.227031,36.592307 201.247672,37.2712372 C201.265968,37.8870512 201.045868,38.4817235 200.624204,38.965306 L200.491695,39.1069581 L196.61015,43.0674698 C196.070903,43.738214 195.479537,43.9101209 195.075489,43.9346791 C194.631707,43.9638419 193.948489,43.8400279 193.211089,43.104307 C189.110233,39.5377488 183.550573,37.3868651 178.377932,37.3868651 C166.497473,37.3868651 156.832313,47.3912372 156.832313,59.6902605 C156.832313,71.9391442 166.536691,81.9036093 178.465656,81.9036093 C184.98306,81.9036093 189.441521,79.1664 193.288493,76.2076558 C194.248137,75.4631564 195.407394,75.3973393 196.287574,76.0263001 L196.431605,76.1375628 L200.574775,80.1784 C200.993787,80.5426791 201.253348,81.1044465 201.273989,81.7317023 C201.297211,82.4546326 201.004624,83.1918884 200.490662,83.7040279 C194.509925,89.4971907 186.83456,92.5551907 178.288143,92.5551907 C160.123525,92.5551907 145.34455,77.8919349 145.34455,59.8677953 C145.34455,41.7454233 160.123525,27.0013302 178.288143,27.0013302 Z M339.344545,27.0013302 C347.854324,27.0013302 354.660702,29.6111442 361.417026,35.4610977 C361.970721,35.9507256 362.282401,36.5917953 362.303042,37.2712372 C362.322275,37.886586 362.101834,38.4807932 361.680488,38.9650638 L361.548096,39.1069581 L357.665519,43.0674698 C357.126272,43.738214 356.535423,43.9101209 356.130859,43.9346791 C355.684497,43.9638419 355.004891,43.8400279 354.266458,43.104307 C350.166119,39.5377488 344.605942,37.3868651 339.432269,37.3868651 C327.552327,37.3868651 317.887683,47.3912372 317.887683,59.6902605 C317.887683,71.9391442 327.593093,81.9036093 339.522058,81.9036093 C346.038946,81.9036093 350.497407,79.1664 354.344378,76.2076558 C355.304023,75.4631564 356.46328,75.3973393 357.34346,76.0263001 L357.48749,76.1375628 L361.63066,80.1784 C362.049157,80.5426791 362.308718,81.1044465 362.329875,81.7311907 C362.353612,82.4536093 362.061026,83.1908651 361.548096,83.7030047 C355.565811,89.4971907 347.889929,92.5551907 339.344545,92.5551907 C321.178894,92.5551907 306.400436,77.8919349 306.400436,59.8677953 C306.400436,41.7454233 321.178894,27.0013302 339.344545,27.0013302 Z M224.672398,27.8901814 C225.947518,27.8901814 227.072358,28.9595803 227.160305,30.215247 L227.165834,30.3731116 L227.165834,89.1837163 C227.165834,90.4533721 226.091999,91.5745003 224.830941,91.6621591 L224.672398,91.6676698 L218.795898,91.6676698 C217.521273,91.6676698 216.396453,90.5973278 216.308507,89.3415857 L216.302978,89.1837163 L216.302978,30.3731116 C216.302978,29.1034558 217.376814,27.9832707 218.637414,27.8956873 L218.795898,27.8901814 L224.672398,27.8901814 Z M273.995006,27.8901814 C285.140128,27.8901814 294.206698,36.7756233 294.206698,47.6963209 C294.206698,55.4910959 289.460317,62.382027 281.731395,65.9493372 L281.348887,66.1220884 L293.131817,87.9199953 C293.580759,88.7513907 293.575083,89.7383209 293.116852,90.4970651 C292.697839,91.1909008 291.970009,91.6093033 291.100762,91.6620065 L290.912391,91.6676698 L283.967202,91.6676698 C282.989978,91.6676698 282.227278,91.1024309 281.887446,90.5402272 L281.825179,90.4279953 L270.204798,67.3254372 L258.060134,67.3254372 L258.060134,89.1837163 C258.060134,90.4533721 256.985823,91.5745003 255.724728,91.6621591 L255.566182,91.6676698 L249.777923,91.6676698 C248.458714,91.6676698 247.374911,90.6402358 247.290318,89.3467346 L247.285003,89.1837163 L247.285003,30.3731116 C247.285003,29.0592512 248.316037,27.9797343 249.614303,27.8954751 L249.777923,27.8901814 L273.995006,27.8901814 Z M385.728129,27.8901302 C387.003249,27.8901302 388.128565,28.9595292 388.21655,30.2151959 L388.222081,30.3730605 L388.222081,81.8152 L411.547472,81.8152 C412.867672,81.8152 413.951989,82.8421625 414.036623,84.1351733 L414.04194,84.2981302 L414.04194,89.1836651 C414.04194,90.4985079 413.01043,91.5780641 411.711213,91.6623248 L411.547472,91.6676186 L379.851629,91.6676186 C378.53242,91.6676186 377.448617,90.6406561 377.364024,89.34674 L377.358709,89.1836651 L377.358709,30.3730605 C377.358709,29.0592 378.389743,27.9796831 379.688009,27.895424 L379.851629,27.8901302 L385.728129,27.8901302 Z M464.343139,27.8902326 C465.663339,27.8902326 466.747181,28.917195 466.831776,30.2102058 L466.837091,30.3731628 L466.837091,35.3482326 C466.837091,36.6625842 465.806057,37.7421207 464.506878,37.8263807 L464.343139,37.8316744 L437.010809,37.8316744 L437.010809,54.363907 L459.980142,54.363907 C461.255757,54.363907 462.381093,55.4337774 462.469079,56.6894818 L462.47461,56.8473488 L462.47461,61.821907 C462.47461,63.1362586 461.443576,64.2157951 460.14394,64.3000551 L459.980142,64.3053488 L437.010809,64.3053488 L437.010809,81.8153023 L464.343139,81.8153023 C465.663339,81.8153023 466.747181,82.8422648 466.831776,84.1348229 L466.837091,84.2977209 L466.837091,89.1837674 C466.837091,90.4981191 465.806057,91.5781271 464.506878,91.6624248 L464.343139,91.6677209 L428.729629,91.6677209 C427.409925,91.6677209 426.326102,90.640287 426.241508,89.3467858 L426.236193,89.1837674 L426.236193,30.3731628 C426.236193,29.0593023 427.267227,27.9797855 428.56595,27.8955263 L428.729629,27.8902326 L464.343139,27.8902326 Z M273.283407,38.0981814 L258.237647,38.0981814 L258.237647,58.0946465 L273.283407,58.0946465 C278.736766,58.0946465 283.343843,53.414786 283.343843,47.8743674 C283.343843,42.5749256 278.736766,38.0981814 273.283407,38.0981814 Z" id="Combined-Shape" fill="#FFFFFF"></path>
            </g>
        </svg>
    );
}

interface Metrics {
    current_unique_payers: number;
    current_paid_count: number;
    current_revenue_usdc: number;
    current_buyer_type_counts: {
        human: number;
        agent: number;
    };
    preview_count: number;
    full_count: number;
}

const prefersReducedMotion = () =>
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function HomePage({ onNavigate }: HomeProps) {
    const [metrics, setMetrics] = useState<Metrics>({
        current_unique_payers: 0,
        current_paid_count: 0,
        current_revenue_usdc: 0,
        current_buyer_type_counts: { human: 0, agent: 0 },
        preview_count: 0,
        full_count: 0,
    });

    useEffect(() => {
        async function loadLandingTraction() {
            try {
                const data = await getPlatformSummary();
                const tierCounts = data.tier_counts || {};
                const legacyPaidCount = Number(data.legacy_paid_count || 0);
                const buyerTypes = data.current_buyer_type_counts || (
                    legacyPaidCount === 0 ? data.buyer_type_counts || {} : {}
                );
                setMetrics({
                    current_unique_payers: data.current_unique_payers ?? (legacyPaidCount === 0 ? data.unique_payers || 0 : 0),
                    current_paid_count: data.current_paid_count ?? data.paid_count ?? 0,
                    current_revenue_usdc: data.current_revenue_usdc ?? (legacyPaidCount === 0 ? data.revenue_usdc || 0 : 0),
                    current_buyer_type_counts: {
                        human: Number(buyerTypes.human || 0),
                        agent: Number(buyerTypes.agent || 0),
                    },
                    preview_count: tierCounts.preview || 0,
                    full_count: tierCounts.full || 0,
                });
            } catch (err) {
                console.warn("Landing traction unavailable", err);
            }
        }
        loadLandingTraction();
    }, []);

    // Scroll-triggered entrance animations.
    useEffect(() => {
        const elements = Array.from(document.querySelectorAll<HTMLElement>(".animate-on-scroll"));
        if (elements.length === 0) return;

        if (prefersReducedMotion() || typeof IntersectionObserver === "undefined") {
            elements.forEach((el) => el.classList.add("is-visible"));
            return;
        }

        const reveal = (el: HTMLElement) => el.classList.add("is-visible");
        const isAboveFoldLine = (el: HTMLElement) =>
            el.getBoundingClientRect().top <= window.innerHeight + 40;

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        reveal(entry.target as HTMLElement);
                    }
                });
            },
            { threshold: 0.05, rootMargin: "0px 0px 120px 0px" }
        );

        elements.forEach((el) => {
            if (isAboveFoldLine(el)) {
                reveal(el);
            } else {
                observer.observe(el);
            }
        });

        let sweepScheduled = false;
        const sweep = () => {
            sweepScheduled = false;
            elements.forEach((el) => {
                if (!el.classList.contains("is-visible") && isAboveFoldLine(el)) {
                    reveal(el);
                    observer.unobserve(el);
                }
            });
        };
        const onScroll = () => {
            if (!sweepScheduled) {
                sweepScheduled = true;
                window.requestAnimationFrame(sweep);
            }
        };
        window.addEventListener("scroll", onScroll, { passive: true });

        return () => {
            window.removeEventListener("scroll", onScroll);
            observer.disconnect();
        };
    }, []);

    function compactNumber(value: number) {
        return new Intl.NumberFormat("en-US", {
            notation: value >= 10000 ? "compact" : "standard",
            maximumFractionDigits: 1,
        }).format(value);
    }

    const statTiles = useMemo(() => ([
        { value: compactNumber(metrics.current_paid_count), label: "reports unlocked" },
        { value: `${Number(metrics.current_revenue_usdc).toFixed(2)} USDC`, label: "settled on Arc" },
        { value: compactNumber(metrics.current_unique_payers), label: "active wallets" },
        { value: compactNumber(metrics.current_buyer_type_counts.agent), label: "agent purchases" },
    ]), [metrics]);

    return (
        <div className="landing-page-root">
            <LandingHeader onNavigate={onNavigate} />

            <main className="landing-main-flow">
                {/* SECTION 01: HERO */}
                <section id="hero" className="landing-section landing-section--hero animate-on-scroll">
                    <div className="landing-container">
                        <div className="landing-hero-grid">
                            <div className="landing-hero-copy">
                                <div className="landing-kicker">Quantitative Market Memory for Autonomous Agents</div>
                                <h1 className="landing-hero-title">
                                    Before your agent acts on a signal,{" "}
                                    <span className="serif-line">show it what happened last time.</span>
                                </h1>
                                <p className="landing-hero-desc">
                                    QMA matches live funding and open-interest dislocations against historical regimes,
                                    then sells the statistical evidence as a per-query report — paid in USDC, settled on {ARC_CHAIN.name} via Circle Gateway.
                                </p>
                                <div className="landing-actions">
                                    <button type="button" className="btn-primary landing-primary text-btn" onClick={() => onNavigate("app")}>
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <circle cx="11" cy="11" r="8"></circle>
                                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                                        </svg>
                                        Open Market Workspace
                                    </button>
                                    <button type="button" className="landing-secondary text-btn" onClick={() => onNavigate("traction")}>
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline>
                                            <polyline points="17 6 23 6 23 12"></polyline>
                                        </svg>
                                        See Live Proof
                                    </button>
                                </div>
                                <p className="landing-hero-footnote">
                                    Agents decide to buy, skip, or keep researching — every payment stays inside hard USDC spending caps.
                                </p>
                            </div>

                            <div className="landing-hero-visual">
                                <AgentLoopReplay />
                            </div>
                        </div>
                    </div>
                </section>

                {/* SECTION 02: LIVE TRACTION STATS BAND */}
                <section id="live-proof" className="landing-section landing-section--traction animate-on-scroll" aria-label="Live QMA traction">
                    <div className="landing-container">
                        <div className="landing-traction-header">
                            <div className="section-eyebrow landing-traction-label">
                                <span className="indicator-dot"></span>
                                <span>Live Network Activity</span>
                            </div>
                        </div>
                        <div className="landing-stats-band">
                            {statTiles.map((tile, idx) => (
                                <div className="stat-tile" key={idx}>
                                    <strong className="stat-value">{tile.value}</strong>
                                    <span className="stat-label">{tile.label}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* SECTION 03: THE PROBLEM & CORE THESIS */}
                <section id="why-qma" className="landing-section landing-section--problem animate-on-scroll" aria-label="The problem QMA solves">
                    <div className="landing-container landing-container--narrow">
                        <div className="landing-problem-inner">
                            <div className="section-eyebrow">The Core Thesis</div>
                            <blockquote>
                                "A live signal is <strong>a rumor about the future</strong>. Historical evidence is what turns it into a decision."
                            </blockquote>
                            <p>
                                Funding-rate and open-interest dislocations flood agent feeds every minute. Without
                                precedent, an autonomous agent either overpays for noise or ignores real dislocations.
                                QMA closes that gap: per-query access to matching historical regimes, delivered with the
                                settlement evidence that proves what was bought, from whom, and for how much.
                            </p>
                        </div>
                    </div>
                </section>

                {/* SECTION 04: MEASURED BENCHMARKS */}
                <section id="measured" className="landing-section landing-section--measured animate-on-scroll" aria-label="Measured on live infrastructure">
                    <div className="landing-container">
                        <div className="section-eyebrow landing-section-label">Measured, not claimed</div>
                        <div className="landing-measured">
                            <div className="measure-cell">
                                <span className="measure-value">&lt; 500ms</span>
                                <span className="measure-label">{ARC_CHAIN.name} finality</span>
                            </div>
                            <div className="measure-cell">
                                <span className="measure-value">$0.00002</span>
                                <span className="measure-label">median gas per settlement</span>
                            </div>
                            <div className="measure-cell">
                                <span className="measure-value">$0.002+</span>
                                <span className="measure-label">per-query pricing</span>
                            </div>
                            <div className="measure-cell">
                                <span className="measure-value">100%</span>
                                <span className="measure-label">hash-bound delivery SLA</span>
                            </div>
                        </div>
                    </div>
                </section>

                {/* SECTION 05: CORE PILLARS */}
                <section id="features" className="landing-section landing-section--features animate-on-scroll">
                    <div className="landing-container">
                        <div className="section-eyebrow landing-section-label">Core Capabilities</div>
                        <h2 className="landing-section-title">Built for <span className="serif-accent">High-Frequency</span> Quantitative Reasoning</h2>
                        <div className="landing-grid">
                            <article className="animate-on-scroll delay-100">
                                <div className="feature-icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
                                        <circle cx="12" cy="12" r="3" />
                                    </svg>
                                </div>
                                <h2>Historical Regime Matching</h2>
                                <p className="landing-feature-desc">
                                    Retrieve empirical past market regimes that share the same structural funding and open-interest anomalies across perpetual exchanges.
                                </p>
                            </article>
                            <article className="animate-on-scroll delay-200">
                                <div className="feature-icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <rect x="2" y="5" width="20" height="14" rx="2" />
                                        <path d="M2 10h20" />
                                    </svg>
                                </div>
                                <h2>Statistical Distributions, Not Guarantees</h2>
                                <p className="landing-feature-desc">
                                    Inspect post-anomaly price trajectories and statistical distributions. Evidence-backed decision context with empirical confidence intervals.
                                </p>
                            </article>
                            <article className="animate-on-scroll delay-300">
                                <div className="feature-icon">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                                        <polyline points="10 17 15 12 10 7" />
                                        <line x1="15" y1="12" x2="3" y2="12" />
                                    </svg>
                                </div>
                                <h2>Hard Spending Guardrails on Arc</h2>
                                <p className="landing-feature-desc">
                                    Sub-cent micropayments via Circle Gateway on Arc. Autonomous agents operate within mathematical session budgets without credit card lock-ins.
                                </p>
                            </article>
                        </div>
                    </div>
                </section>

                {/* SECTION 06: HOW IT WORKS / PROOF ARCHITECTURE */}
                <section id="how-it-works" className="landing-section landing-section--proof animate-on-scroll">
                    <div className="landing-container">
                        <div className="landing-proof-layout">
                            <div className="landing-proof-text animate-on-scroll">
                                <div className="section-eyebrow landing-section-label">Agent Infrastructure</div>
                                <h2 className="landing-section-title">Machine-Readable <span className="serif-accent">Market Memory</span> for AI Agents</h2>
                                <p className="landing-proof-desc">
                                    Raw anomaly signals answer "What is happening now?", but lack historical precedent. QMA packages
                                    empirical market regime distributions into queryable API reports. Agents use one x402 authorization,
                                    and report delivery is cryptographically verified against the bound hash on {ARC_CHAIN.name}.
                                </p>
                                <div className="landing-terminal" aria-label="qma CLI example">
                                    <div className="landing-terminal-bar">
                                        <span className="landing-terminal-dot dot-red" />
                                        <span className="landing-terminal-dot dot-amber" />
                                        <span className="landing-terminal-dot dot-green" />
                                        <span className="landing-terminal-title">agents/bin/qma.js</span>
                                    </div>
                                    <pre className="landing-terminal-body"><code><span className="t-prompt">$</span> qma agent run <span className="t-flag">\</span>
                                        <span className="t-flag">--live</span> <span className="t-flag">--executor</span> circle-agent-wallet <span className="t-flag">--wallet</span> 0xYour-Agent-Wallet <span className="t-flag">--no-auto-deposit</span> <span className="t-flag">\</span>
                                        <span className="t-flag">--task</span> <span className="t-str">"buy the best BTC preview"</span> <span className="t-flag">--budget</span> 0.01 <span className="t-flag">--max-price</span> 0.005 <span className="t-flag">--max-purchases</span> 1

                                        <span className="t-out">{'#'}</span> {metrics ? `${metrics.current_paid_count} reports settled for ${Number(metrics.current_revenue_usdc).toFixed(2)} USDC on ${ARC_CHAIN.name}, every verdict hash-linked` : 'connecting to the live ledger...'}</code></pre>
                                </div>
                            </div>
                            <div className="landing-proof-card animate-on-scroll delay-200">
                                <div className="landing-proof-item"><span className="landing-proof-label">Active Providers</span><strong className="landing-proof-value">Funding Memory, OI Memory, Pyth</strong></div>
                                <div className="landing-proof-item"><span className="landing-proof-label">Approach</span><strong className="landing-proof-value">Match live anomalies to historical regimes</strong></div>
                                <div className="landing-proof-item"><span className="landing-proof-label">Pricing</span><strong className="landing-proof-value">Pay per query ($0.002 preview / $0.005 full)</strong></div>
                                <div className="landing-proof-item"><span className="landing-proof-label">Budget Safety</span><strong className="landing-proof-value">Strict session spending caps in USDC</strong></div>
                                <div className="landing-proof-item"><span className="landing-proof-label">Payment Rail</span><strong className="landing-proof-value">Circle Gateway Nanopayments on {ARC_CHAIN.name}</strong></div>
                                <div className="landing-proof-item"><span className="landing-proof-label">Audit Engine</span><strong className="landing-proof-value">Athenian Euthyna Cryptographic Hash Chain</strong></div>
                                <div className="landing-proof-item proof-tech"><span className="landing-proof-label">Execution Status</span><strong className="landing-proof-value">Live On-Chain Settlement</strong></div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* SECTION 07: AUDIENCES / WHO IT'S FOR */}
                <section id="audiences" className="landing-section landing-section--audiences animate-on-scroll">
                    <div className="landing-container">
                        <div className="section-eyebrow landing-section-label animate-on-scroll">Who it's for</div>
                        <h2 className="landing-section-title">Designed for <span className="serif-accent">Machines &amp; Quants</span></h2>
                        <div className="landing-audience-grid">
                            <article className="landing-audience-card--agents animate-on-scroll delay-100">
                                <strong className="landing-audience-title">Autonomous AI Agents</strong>
                                <p className="landing-audience-desc">Query market memory on-demand, evaluate analog distributions, and enforce hard spending policies via SDK or CLI.</p>
                            </article>
                            <article className="landing-audience-card--researchers animate-on-scroll delay-200">
                                <strong className="landing-audience-title">Quant Developers</strong>
                                <p className="landing-audience-desc">Integrate historical regime lookups directly into automated research pipelines without recurring SaaS credit cards.</p>
                            </article>
                            <article className="landing-audience-card--traders animate-on-scroll delay-300">
                                <strong className="landing-audience-title">Data Creators</strong>
                                <p className="landing-audience-desc">Monetize custom quantitative indicators. Earn USDC per query with cryptographic proof of delivery and on-demand claims.</p>
                            </article>
                        </div>
                    </div>
                </section>

                {/* SECTION 08: AGENT-NATIVE CLI & SDK TERMINAL */}
                <section id="builders" className="landing-section landing-section--builders animate-on-scroll">
                    <div className="landing-container">
                        <div className="landing-agent-api-layout">
                            <div className="animate-on-scroll">
                                <div className="section-eyebrow landing-section-label">Agent-Native CLI &amp; SDK</div>
                                <h2 className="landing-section-title">External agents can purchase reports <span className="serif-accent">programmatically</span></h2>
                                <p>
                                    An agent can evaluate ranked anomalies, request an invoice, settle the x402 payment,
                                    and receive structured JSON evidence within its strict spending policy.
                                </p>
                                <div className="landing-actions">
                                    <a className="landing-secondary" href="/docs" target="_blank" rel="noopener noreferrer">Open API Docs</a>
                                    <a className="landing-secondary" href="https://github.com/hoanlv214/qma" target="_blank" rel="noopener noreferrer">View GitHub SDK</a>
                                </div>
                            </div>
                            <div className="agent-terminal animate-on-scroll delay-200" aria-label="Example structured evidence response">
                                <div className="mac-window-header">
                                    <span className="mac-dot mac-red"></span>
                                    <span className="mac-dot mac-yellow"></span>
                                    <span className="mac-dot mac-green"></span>
                                    <span className="mac-title">evidence.json</span>
                                </div>
                                <pre className="agent-terminal-pre">
                                    <code>
                                        <span className="terminal-line">{`{`}</span>
                                        <span className="terminal-line">{'  "symbol": "HYPE_USDT",'}</span>
                                        <span className="terminal-line">{'  "regime_cluster": "high_vol_drawdown",'}</span>
                                        <span className="terminal-line">{'  "analog_win_rate": 0.61,'}</span>
                                        <span className="terminal-line">{'  "ci_95": [0.48, 0.73],'}</span>
                                        <span className="terminal-line">{'  "samples": 34,'}</span>
                                        <span className="terminal-line">{'  "verdict": "VALID"'}</span>
                                        <span className="terminal-line">{`}`}</span>
                                    </code>
                                </pre>
                            </div>
                        </div>
                    </div>
                </section>

                {/* SECTION 09: CREATORS & DATA MONETIZATION */}
                <section id="creators" className="landing-section landing-section--creators animate-on-scroll">
                    <div className="landing-container">
                        <div className="landing-builders-layout">
                            <div>
                                <div className="section-eyebrow landing-section-label">For Quants &amp; Data Creators</div>
                                <h2 className="landing-section-title">Monetize <span className="serif-accent">Quantitative Datasets</span></h2>
                            </div>
                            <div>
                                <p className="landing-builders-desc">
                                    Package historical datasets into query-based intelligence APIs. QMA handles x402 settlement,
                                    query/report hash binding, and creator earnings accounting after valid delivery. Claim your USDC earnings on-demand.
                                </p>
                                <div className="landing-actions landing-actions--mt-lg">
                                    <button type="button" className="landing-secondary text-btn" onClick={() => onNavigate("marketplace")}>Join Provider Beta</button>
                                    <a className="landing-secondary" href="/docs" target="_blank" rel="noopener noreferrer">View API Docs</a>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                {/* SECTION 10: OPEN SOURCE ECOSYSTEM */}
                <section id="source-code" className="landing-section landing-section--source animate-on-scroll">
                    <div className="landing-container">
                        <div className="landing-source-inner">
                            <div className="section-eyebrow landing-section-label">Open Source Ecosystem</div>
                            <h2 className="landing-section-title">Autonomous Agent Commerce on Arc</h2>
                            <p className="landing-source-desc">
                                QMA is open-source. Build your own provider plugin, customize the analog matching engine, or integrate the
                                payment middleware. The repository includes everything you need to run autonomous buyer agents and monetize quantitative feeds.
                            </p>
                            <div className="landing-actions landing-actions--mt-md">
                                <a className="landing-secondary" href="https://github.com/hoanlv214/qma" target="_blank" rel="noopener noreferrer">View GitHub Repository</a>
                            </div>
                        </div>
                    </div>
                </section>

                {/* SECTION 11: GLOBAL LANDING FOOTER */}
                <footer className="landing-section landing-section--footer">
                    <div className="landing-container">
                        <div className="landing-footer-cols--4">
                            <div className="footer-col-brand">
                                <a href="/" className="logo-item qma-logo-item" title="QMA" onClick={(e) => e.preventDefault()}>
                                    <QmaLogo size={28} showText={true} />
                                </a>
                                <p className="footer-brand-desc">Historical market intelligence &amp; autonomous agent commerce on Arc. Evidence-backed reports from past analog events.</p>
                                <div className="footer-socials" aria-label="QMA footer social links">
                                    <a className="social-link" href="http://x.com/hoanlv21" target="_blank" rel="noopener noreferrer" title="X (Twitter)">
                                        <svg viewBox="0 0 24 24" fill="currentColor">
                                            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                                        </svg>
                                    </a>
                                    <a className="social-link" href="https://github.com/hoanlv214/qma" target="_blank" rel="noopener noreferrer" title="GitHub">
                                        <svg viewBox="0 0 24 24" fill="currentColor">
                                            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.11.82-.26.82-.577v-2.234c-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22v3.293c0 .319.22.694.825.576C20.565 21.795 24 17.3 24 12c0-6.63-5.37-12-12-12z" />
                                        </svg>
                                    </a>
                                    <a className="social-link" href="https://discordapp.com/users/711257217483014206" target="_blank" rel="noopener noreferrer" title="Discord">
                                        <svg viewBox="0 0 127.14 96.36" fill="currentColor">
                                            <path d="M107.7,8.07A105.15,105.15,0,0,0,77.26,0a77.19,77.19,0,0,0-3.3,6.83A96.67,96.67,0,0,0,53.22,6.83,77.19,77.19,0,0,0,49.88,0,105.15,105.15,0,0,0,19.44,8.07C3.66,31.58-1.86,54.65,1,77.53A105.73,105.73,0,0,0,32,96.36a77.7,77.7,0,0,0,6.63-10.85,68.43,68.43,0,0,1-10.5-5c.9-.65,1.76-1.34,2.58-2.07a75.79,75.79,0,0,0,73,0c.82.73,1.68,1.42,2.58,2.07a68.43,68.43,0,0,1-10.5,5,77.7,77.7,0,0,0,6.63,10.85,105.73,105.73,0,0,0,31-18.83C129.87,54.65,124.34,31.58,107.7,8.07ZM42.45,65.69C36.18,65.69,31,60,31,53S36.18,40.36,42.45,40.36,53.83,46,53.83,53,48.72,65.69,42.45,65.69Zm42.24,0C78.41,65.69,73.24,60,73.24,53S78.41,65.69,84.69,65.69,96.07,46,96.07,53,91,65.69,84.69,65.69Z" />
                                        </svg>
                                    </a>
                                </div>
                            </div>
                            <div className="landing-footer-col">
                                <h3>Product</h3>
                                <button type="button" className="footer-link-btn" onClick={() => onNavigate("app")}>Market Workspace</button>
                                <button type="button" className="footer-link-btn" onClick={() => onNavigate("swap")}>Swap / StableFX</button>
                                <button type="button" className="footer-link-btn" onClick={() => onNavigate("traction")}>Live Proof &amp; Ledger</button>
                                <button type="button" className="footer-link-btn" onClick={() => onNavigate("profile")}>Wallet History</button>
                            </div>
                            <div className="landing-footer-col">
                                <h3>Platform</h3>
                                <button type="button" className="footer-link-btn" onClick={() => onNavigate("marketplace")}>Creator Marketplace</button>
                                <a href={`${API_BASE_URL}/api/v1/providers`} target="_blank" rel="noopener noreferrer">Provider API</a>
                                <a href="/docs" target="_blank" rel="noopener noreferrer">API Docs</a>
                                <a href="https://testnet.arcscan.app/" target="_blank" rel="noopener noreferrer">Arcscan Explorer</a>
                            </div>
                            <div className="landing-footer-col">
                                <h3>Developers</h3>
                                <a href="https://github.com/hoanlv214/qma" target="_blank" rel="noopener noreferrer">GitHub Repository</a>
                                <a href="https://github.com/hoanlv214/qma/blob/main/examples/README.md" target="_blank" rel="noopener noreferrer">Agent Examples</a>
                                <a href="/docs" target="_blank" rel="noopener noreferrer">OpenAPI Docs</a>
                                <a href={`${API_BASE_URL}/openapi.json`} target="_blank" rel="noopener noreferrer">OpenAPI Spec</a>
                            </div>
                        </div>

                        <div className="landing-footer-builton">
                            <span className="landing-settlement-label">Built on</span>
                            <div className="landing-settlement-logos">
                                <a href={ARC_CHAIN.explorerUrl} target="_blank" rel="noopener noreferrer" title={ARC_CHAIN.name}>
                                    <ArcLogoSvg />
                                </a>
                                <a href="https://www.circle.com/" target="_blank" rel="noopener noreferrer" title="Circle Gateway">
                                    <CircleLogoSvg />
                                </a>
                            </div>
                            <p className="landing-settlement-copy">Built independently on {ARC_CHAIN.name}. USDC &amp; EURC settlement via Circle Gateway.</p>
                        </div>

                        <div className="landing-footer-bottom">
                            <span>2026 QMA Network. All rights reserved. Historical analogs only. Not financial advice. Running on {ARC_CHAIN.name}.</span>
                            <span className="landing-status-dot">{ARC_CHAIN.name} live</span>
                        </div>
                        <p className="landing-brand-disclaimer">
                            Circle, Arc and related marks are trademarks of Circle Internet Group, Inc. and/or its affiliates.
                            QMA is an independent application and is not endorsed or sponsored by Circle.
                        </p>
                    </div>
                </footer>
            </main>
        </div>
    );
}

export { HomePage as LandingPage };
export default HomePage;
