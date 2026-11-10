import React from "react";
import "./careerPrint.css";

const choices = {yes:"بله",no:"خیر",male:"مرد",female:"زن",healthy:"سالم",condition:"دارای بیماری / محدودیت",completed:"پایان خدمت",subject:"مشمول",exempt:"معاف",serving:"در حال خدمت",fulltime:"تمام‌وقت",parttime:"پاره‌وقت",project:"همکاری پروژه‌ای / خارج شرکت",single:"مجرد",married:"متأهل",new:"جدید",reviewing:"در حال بررسی",interview:"دعوت به مصاحبه",accepted:"تأیید اولیه",rejected:"رد شده",archived:"بایگانی"};
const display = value => value === undefined || value === null || value === "" ? "—" : choices[value] || String(value);
const TABLES = [
 ["۱- اطلاعات شخصی",[["gender","جنسیت"],["father_name","نام پدر"],["national_id","کد ملی"],["birth_date","تاریخ تولد"],["birth_certificate_number","شماره شناسنامه"],["birth_certificate_city","محل صدور شناسنامه"],["birth_place","محل تولد"],["nationality","ملیت"],["religion","دین"],["denomination","مذهب"],["marital_status","وضعیت تأهل"],["spouse_name","نام همسر"],["health_status","سلامت جسمانی"],["health_details","نوع بیماری / محدودیت"],["had_surgery","سابقه عمل جراحی"],["surgery_details","شرح عمل جراحی"],["smokes","مصرف سیگار"],["military_status","وضعیت نظام وظیفه"],["military_exemption_reason","علت معافیت"]]],
 ["۶- نحوه همکاری",[["employment_type","نوع همکاری"],["available_from","آمادگی شروع به کار"],["night_shift","آمادگی شیفت شب"]]],
 ["۷- بیمه",[["has_insurance","سابقه بیمه"],["insurance_duration","مدت سابقه بیمه"],["insurance_number","شماره بیمه"]]],
 ["۸- نحوه آشنایی با سازمان",[["referral_source","نحوه آشنایی"],["referral_name","نام معرف"]]],
 ["۱۰- وضعیت شغلی کنونی",[["employed_now","در حال حاضر شاغل است"],["has_work_experience","سابقه کار دارد"],["reason_for_leaving","دلیل تمایل به ترک کار"]]],
 ["۱۱- اطلاعات دیگر",[["travel_ready","آمادگی مأموریت"],["positive_trait","ویژگی مثبت"],["negative_trait","ویژگی قابل بهبود"],["internal_contact","آشنای شاغل در شرکت"],["expected_salary","حقوق درخواستی (ریال)"],["extra_notes","توضیحات تکمیلی"]]],
 ["۱۳- اطلاعات تماس و سکونت",[["city","شهر محل سکونت"],["housing_type","وضعیت سکونت"],["address","نشانی"],["landline","تلفن ثابت"]]],
];
const REPEATS = [
 ["۲- سوابق تحصیلی","education_history",[["degree","مدرک"],["field","رشته"],["institution","نام مؤسسه"],["average","معدل"],["start_date","شروع"],["end_date","پایان"]]],
 ["۳- سوابق کاری","work_history",[["company","نام سازمان"],["position","سمت"],["duration","مدت"],["start_date","شروع"],["end_date","پایان"],["last_salary","آخرین حقوق"],["phone","تلفن"],["leaving_reason","علت ترک"]]],
 ["۴- دوره‌های آموزشی و مهارت‌ها","training_history",[["title","نام دوره"],["institution","مؤسسه"],["duration","مدت"],["start_date","شروع"],["end_date","پایان"]]],
 ["۹- مشخصات دو نفر از دوستان، همکاران یا آشنایان","references",[["full_name","نام و نام خانوادگی"],["relationship","نسبت"],["address","نشانی"],["phone","تلفن"]]],
 ["۱۲- افراد تحت تکفل","dependents",[["full_name","نام و نام خانوادگی"],["gender","جنسیت"],["relationship","نسبت"],["birth_date","تاریخ تولد"],["education","تحصیلات"],["occupation","شغل"]]],
];
const PairTable = ({fields, data}) => <table className="career-print-table career-pair-table"><tbody>{fields.map(([k,label],i)=>i%2===0&&<tr key={k}><th>{label}</th><td>{display(data[k])}</td>{fields[i+1]?<><th>{fields[i+1][1]}</th><td>{display(data[fields[i+1][0]])}</td></>:<><th/><td/></>}</tr>)}</tbody></table>;
const GridTable = ({columns,rows}) => <table className="career-print-table"><thead><tr>{columns.map(([k,label])=><th key={k}>{label}</th>)}</tr></thead><tbody>{rows.length?rows.map((row,i)=><tr key={i}>{columns.map(([k])=><td key={k}>{display(row[k])}</td>)}</tr>):<tr><td colSpan={columns.length} className="career-empty-row">—</td></tr>}</tbody></table>;
const Block = ({title,children}) => <section className="career-print-section"><h3>{title}</h3>{children}</section>;

export default function CareerPrintDocument({record}) {
 const d=record.details||{};
 const table=(i)=><Block key={TABLES[i][0]} title={TABLES[i][0]}><PairTable fields={TABLES[i][1]} data={d}/></Block>;
 const repeat=(i)=><Block key={REPEATS[i][0]} title={REPEATS[i][0]}><GridTable columns={REPEATS[i][2]} rows={Array.isArray(d[REPEATS[i][1]])?d[REPEATS[i][1]]:[]}/></Block>;
 return <article className="career-print-document" dir="rtl">
   <header className="career-print-head"><div className="career-print-company">شرکت تولیدی صنعتی فواد الیاف <span>(FAIPCO)</span></div><h2>پرسشنامه استخدامی</h2><div className="career-print-meta"><span>شماره پرونده: {record.id}</span><span>تاریخ ثبت: {new Date(record.created_at).toLocaleDateString("fa-IR")}</span></div></header>
   <table className="career-print-table career-pair-table"><tbody><tr><th>نام و نام خانوادگی</th><td>{record.full_name}</td><th>شماره همراه</th><td dir="ltr">{record.mobile}</td></tr><tr><th>شغل درخواستی</th><td>{record.requested_position}</td><th>وضعیت بررسی</th><td>{display(record.status)}</td></tr></tbody></table>
   {table(0)}
   <Block title="۲- سوابق تحصیلی"><PairTable fields={[["education","آخرین مدرک تحصیلی"],["field_of_study","رشته و گرایش"],["university","مؤسسه آموزشی"]]} data={d}/><GridTable columns={REPEATS[0][2]} rows={Array.isArray(d.education_history)?d.education_history:[]}/></Block>
   {repeat(1)}
   <Block title="۴- مهارت‌ها، زبان‌های خارجی و دوره‌های آموزشی"><PairTable fields={[["skills","مهارت و تخصص اصلی"],["languages","زبان‌های خارجی"],["computer_skills","نرم‌افزارها"]]} data={d}/><GridTable columns={REPEATS[2][2]} rows={Array.isArray(d.training_history)?d.training_history:[]}/></Block>
   {table(1)}{table(2)}{table(3)}{repeat(3)}{table(4)}{table(5)}{repeat(4)}{table(6)}
   <Block title="تأیید اطلاعات توسط متقاضی"><p>اینجانب صحت اطلاعات ارائه‌شده را تأیید کرده‌ام و اطلاع دارم که تکمیل پرسشنامه تعهدی برای استخدام از سوی شرکت ایجاد نمی‌کند.</p><p>تأیید الکترونیکی هنگام ارسال فرم ثبت شده است.</p></Block>
   <Block title="نظریه واحد اداری / منابع انسانی"><div className="career-print-hr-note">{record.hr_note||"هنوز نظری ثبت نشده است."}</div></Block>
   <footer className="career-print-footer">فواد الیاف – پرسشنامه استخدامی – استفاده محرمانه در واحد منابع انسانی</footer>
 </article>;
}
