<div align="center">
<a href="https://health.ascratech.com">
    <img src="" height="128" alt="Ascra Helathcare" />
  </a>
  <h2>Ascra Healthcare</h2>
  <p align="center">
    <p>Ascra Healthcare open Source, Enterprise and Modern Health Information System.</p>
  </p>

  [Ascra Healthcare](https://health.ascratech.com)

</div>

### Introduction

Ascra Healthcare enables the Healthcare domain in ERPNext and has various features that will help Healthcare practitioners, clinics and hospitals to leverage the power of Frappe and ERPNext. It is built on Frappe, a full-stack, meta-data driven, web framework, and integrates seamlessly with ERPNext, the most agile ERP software. Ascra Healthcare helps to manage Healthcarecare workflows efficiently and most of the design is based on HL7 FHIR (Fast Healthcare  Interoperability Resources).


### Key Features

![Key Features](https://github.com/Ascra-Tech/ascra_healthcare/blob/develop/kea-features.png)

Key feature sets include Patient management, Outpatient / Inpatient management, Clinical Procedures, Rehabilitation and Physiotherapy, Laboratory management etc. and supports configuring multiple Medical Code Standards. It allows mapping any healthcare facility as Service Units and specialities as Medical Departments.

By integrating with ERPNext, features of ERPNext can also be utilized to manage Pharmacy and supplies, Purchases, Human Resources, Accounts and Finance, Asset Management, Quality etc. Along with authentication and role based access permissions, RESTfullness, extensibility, responsiveness and other goodies, the framework also allows setting up Website, payment integration and Patient portal.


### Installation

Using bench, [install ERPNext](https://github.com/frappe/bench#installation) as mentioned here.

Once ERPNext is installed, add health app to your bench by running

```sh
$ bench get-app --branch branch-name https://github.com/Ascra-Tech/ascra_healthcare.git
```

After that, you can install health app on required site by running

```sh
$ bench --site demo.com install-app healthcare
```


### Documentation

Complete documentation for Ascra Healthcare  is available at https://health.ascratech.com/docs



### Credits

Ascra Healthcare  module is developed & maintained by [Ascra Technologies](https://ascratech.com).
