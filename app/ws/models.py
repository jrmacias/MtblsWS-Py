from flask_restful import fields
from isatools.model import Person, OntologyAnnotation, OntologySource, Protocol
from isatools.model import ProtocolParameter, StudyFactor, Comment, Publication
from isatools.model import Sample, Characteristic, FactorValue, Source, Material
import json


Comment_api_model = {
    # name      (str):
    # value     (str, int, float, NoneType):
    'name': fields.String,
    'value': fields.String
}


def serialize_comment(isa_obj):
    assert isinstance(isa_obj, Comment)
    return {
        'name': isa_obj.name,
        'value': isa_obj.value
    }


def unserialize_comment(json_obj):
    name = ''
    if 'name' in json_obj and json_obj['name'] is not None:
        name = json_obj['name']
    value = ''
    if 'value' in json_obj and json_obj['value'] is not None:
        value = json_obj['value']

    return Comment(name=name,
                   value=value)


OntologySource_api_model = {
    # name          (str):
    # file          (str):
    # version       (str):
    # description   (str):
    # comments      (list, comment):
    'name': fields.String,
    'file': fields.String,
    'version': fields.String,
    'description': fields.String,
    'comments': fields.List(fields.Nested(Comment_api_model))
}


def serialize_ontology_source(isa_obj):
    assert isinstance(isa_obj, OntologySource)
    return {
        'name': isa_obj.name,
        'file': isa_obj.file,
        'version': isa_obj.version,
        'description': isa_obj.description,
        'comments': json.loads(json.dumps(isa_obj.comments, default=serialize_comment, sort_keys=True))
    }


def unserialize_ontology_source(json_obj):
    name = ''
    if 'name' in json_obj and json_obj['name'] is not None:
        name = json_obj['name']
    file = ''
    if 'name' in json_obj and json_obj['file'] is not None:
        file = json_obj['file']
    version = ''
    if 'version' in json_obj and json_obj['version'] is not None:
        version = json_obj['version']
    description = ''
    if 'description' in json_obj and json_obj['description'] is not None:
        description = json_obj['description']
    comments = list()
    if 'comments' in json_obj and json_obj['comments'] is not None:
        for comment in json_obj['comments']:
            comments.append(unserialize_comment(comment))

    return OntologySource(name=name,
                          file=file,
                          version=version,
                          description=description,
                          comments=comments)


OntologyAnnotation_api_model = {
    # term -> annotationValue           (str):
    # term_source -> termSource         (OntologySource):
    # term_accession -> termAccession   (str):
    # comments                          (list, Comment):
    'annotationValue': fields.String(attribute='term'),
    'termSource': fields.Nested(OntologySource_api_model, attribute='term_source'),
    'termAccession': fields.String(attribute='term_accession'),
    'comments': fields.List(fields.Nested(Comment_api_model))
}


def serialize_ontology_annotation(isa_obj):
    assert isinstance(isa_obj, OntologyAnnotation)
    term_source = None
    if hasattr(isa_obj, 'term_source') and isa_obj.term_source is not None:
        term_source = serialize_ontology_source(isa_obj.term_source)
    return {
        'annotationValue': isa_obj.term,
        'termSource': term_source,
        'termAccession': isa_obj.term_accession,
        'comments': json.loads(json.dumps(isa_obj.comments, default=serialize_comment, sort_keys=True))
    }


def unserialize_ontology_annotation(json_obj):
    term = ''
    if 'term' in json_obj and json_obj['term'] is not None:
        term = json_obj['term']
    term_source = None
    if 'term_source' in json_obj and json_obj['term_source'] is not None:
        term_source = unserialize_ontology_source(json_obj['term_source'])
    term_accession = ''
    if 'term_accession' in json_obj and json_obj['term_accession'] is not None:
        term_accession = json_obj['term_accession']
    comments = list()
    if 'comments' in json_obj and json_obj['comments'] is not None:
        for comment in json_obj['comments']:
            comments.append(unserialize_comment(comment))

    return OntologyAnnotation(term=term,
                              term_source=term_source,
                              term_accession=term_accession,
                              comments=comments)


ProtocolParameter_api_model = {
    # parameter_name -> parameterName   (OntologyAnnotation):
    # unit                              (OntologyAnnotation):
    # comments                          (list, Comment):
    'parameterName': fields.Nested(OntologyAnnotation_api_model, attribute='parameter_name'),
    'unit': fields.Nested(OntologyAnnotation_api_model),
    'comments': fields.List(fields.Nested(Comment_api_model))
}


def serialize_protocol_parameter(isa_obj):
    assert isinstance(isa_obj, ProtocolParameter)
    parameter_name = None
    if hasattr(isa_obj, 'parameter_name') and isa_obj.parameter_name is not None:
        parameter_name = serialize_ontology_annotation(isa_obj.parameter_name)
    unit = None
    if hasattr(isa_obj, 'unit') and isa_obj.unit is not None:
        unit = serialize_ontology_annotation(isa_obj.unit)
    return {
        'parameterName': parameter_name,
        'unit': unit,
        'comments': json.loads(json.dumps(isa_obj.comments, default=serialize_comment, sort_keys=True))
    }


def unserialize_protocol_parameter(json_obj):
    parameter_name = OntologyAnnotation()
    if 'parameter_name' in json_obj and json_obj['parameter_name'] is not None:
        parameter_name = unserialize_ontology_annotation(json_obj['parameter_name'])
    unit = OntologyAnnotation()
    if 'unit' in json_obj and json_obj['unit'] is not None:
        unit = unserialize_ontology_annotation(json_obj['unit'])
    comments = list()
    if 'comments' in json_obj and json_obj['comments'] is not None:
        for comment in json_obj['comments']:
            comments.append(unserialize_comment(comment))

    return ProtocolParameter(parameter_name=parameter_name,
                             # unit=unit,
                             comments=comments)


Protocol_api_model = {
    # name                              (str):
    # protocol_type -> protocolType     (OntologyAnnotation):
    # description                       (str):
    # uri                               (str):
    # version                           (str):
    # parameters                        (list, ProtocolParameter):
    # components                        (list, OntologyAnnotation):
    # comments                          (list, comment):
    'name': fields.String,
    'protocolType': fields.Nested(OntologyAnnotation_api_model, attribute='protocol_type'),
    'description': fields.String,
    'uri': fields.String,
    'version': fields.String,
    'parameters': fields.List(fields.Nested(ProtocolParameter_api_model)),
    'components': fields.List(fields.Nested(OntologyAnnotation_api_model)),
    'comments': fields.List(fields.Nested(Comment_api_model))
}


def serialize_protocol(isa_obj):
    assert isinstance(isa_obj, Protocol)
    return {
        'name': isa_obj.name,
        'protocolType': json.loads(json.dumps(isa_obj.protocol_type,
                                              default=serialize_ontology_annotation, sort_keys=True)),
        'description': isa_obj.description,
        'uri': isa_obj.uri,
        'version': isa_obj.version,
        'parameters': json.loads(json.dumps(isa_obj.parameters,
                                            default=serialize_protocol_parameter, sort_keys=True)),
        'components': json.loads(json.dumps(isa_obj.components,
                                            default=serialize_ontology_annotation, sort_keys=True)),
        'comments': json.loads(json.dumps(isa_obj.comments,
                                          default=serialize_comment, sort_keys=True))
    }


def unserialize_protocol(json_obj):
    name = ''
    if 'name' in json_obj and json_obj['name'] is not None:
        name = json_obj['name']
    protocol_type = OntologyAnnotation()
    if 'protocol_type' in json_obj and json_obj['protocol_type'] is not None:
        protocol_type = unserialize_ontology_annotation(json_obj['protocol_type'])
    description = ''
    if 'description' in json_obj and json_obj['description'] is not None:
        description = json_obj['description']
    uri = ''
    if 'uri' in json_obj and json_obj['uri'] is not None:
        uri = json_obj['uri']
    version = ''
    if 'version' in json_obj and json_obj['version'] is not None:
        version = json_obj['version']
    parameters = list()
    if 'parameters' in json_obj:
        for parameter in json_obj['parameters']:
            parameters.append(unserialize_protocol_parameter(parameter))
    components = list()
    if len(json_obj['components']) > 0:
        for comp in json_obj['components']:
            components.append(unserialize_ontology_annotation(comp))
    comments = list()
    if 'comments' in json_obj and json_obj['comments'] is not None:
        for comment in json_obj['comments']:
            comments.append(unserialize_comment(comment))

    return Protocol(name=name,
                    protocol_type=protocol_type,
                    description=description,
                    uri=uri,
                    version=version,
                    parameters=parameters,
                    components=components,
                    comments=comments)


Person_api_model = {
    # last_name -> lastName         (str):
    # first_name -> firstName       (str):
    # mid_initials -> midInitials   (str):
    # email                         (str):
    # phone                         (str):
    # fax                           (str):
    # address                       (str):
    # affiliation                   (str):
    # roles                         (list, OntologyAnnotation):
    # comments                      (list, Comment):
    'lastName': fields.String(attribute='last_name'),
    'firstName': fields.String(attribute='first_name'),
    'midInitials': fields.String(attribute='mid_initials'),
    'email': fields.String,
    'phone': fields.String,
    'fax': fields.String,
    'address': fields.String,
    'affiliation': fields.String,
    'roles': fields.List(fields.Nested(OntologyAnnotation_api_model)),
    'comments': fields.List(fields.Nested(Comment_api_model))
}


def serialize_person(isa_obj):
    assert isinstance(isa_obj, Person)
    return {
        'lastName': isa_obj.last_name,
        'firstName': isa_obj.first_name,
        'midInitials': isa_obj.mid_initials,
        'email': isa_obj.email,
        'phone': isa_obj.phone,
        'fax': isa_obj.fax,
        'address': isa_obj.address,
        'affiliation': isa_obj.affiliation,
        'roles': json.loads(json.dumps(isa_obj.roles, default=serialize_ontology_annotation, sort_keys=True)),
        'comments': json.loads(json.dumps(isa_obj.comments, default=serialize_comment, sort_keys=True))
    }


def unserialize_person(json_obj):
    last_name = ''
    if 'last_name' in json_obj and json_obj['last_name'] is not None:
        last_name = json_obj['last_name']
    first_name = ''
    if 'first_name' in json_obj and json_obj['first_name'] is not None:
        first_name = json_obj['first_name']
    mid_initials = ''
    if 'mid_initials' in json_obj and json_obj['mid_initials'] is not None:
        mid_initials = json_obj['mid_initials']
    email = ''
    if 'email' in json_obj and json_obj['email'] is not None:
        email = json_obj['email']
    phone = ''
    if 'phone' in json_obj and json_obj['phone'] is not None:
        phone = json_obj['phone']
    fax = ''
    if 'fax' in json_obj and json_obj['fax'] is not None:
        fax = json_obj['fax']
    address = ''
    if 'address' in json_obj and json_obj['address'] is not None:
        address = json_obj['address']
    affiliation = ''
    if 'affiliation' in json_obj and json_obj['affiliation'] is not None:
        affiliation = json_obj['affiliation']
    roles = list()
    if len(json_obj['roles']) > 0:
        for role in json_obj['roles']:
            roles.append(unserialize_ontology_annotation(role))
    comments = list()
    if 'comments' in json_obj and json_obj['comments'] is not None:
        for comment in json_obj['comments']:
            comments.append(unserialize_comment(comment))

    return Person(first_name=first_name,
                  last_name=last_name,
                  mid_initials=mid_initials,
                  email=email,
                  phone=phone,
                  fax=fax,
                  address=address,
                  affiliation=affiliation,
                  roles=roles,
                  comments=comments)


StudyFactor_api_model = {
    # name -> factorName        (str):
    # factor_type -> factorType (OntologyAnnotation):
    # comments                  (list, Comment):
    'factorName': fields.String(attribute='name'),
    'factorType': fields.Nested(OntologyAnnotation_api_model, attribute='factor_type'),
    'comments': fields.List(fields.Nested(Comment_api_model))
}


def serialize_study_factor(isa_obj):
    assert isinstance(isa_obj, StudyFactor)
    return {
        'factorName': isa_obj.name,
        'factorType': json.loads(
            json.dumps(isa_obj.factor_type, default=serialize_ontology_annotation, sort_keys=True)),
        'comments': json.loads(json.dumps(isa_obj.comments, default=serialize_comment, sort_keys=True))
    }


def unserialize_study_factor(json_obj):
    name = ''
    if 'name' in json_obj and json_obj['name'] is not None:
        name = json_obj['name']
    factor_type = OntologyAnnotation()
    if 'factor_type' in json_obj and json_obj['factor_type'] is not None:
        factor_type = unserialize_ontology_annotation(json_obj['factor_type'])
    comments = list()
    if 'comments' in json_obj and json_obj['comments'] is not None:
        for comment in json_obj['comments']:
            comments.append(unserialize_comment(comment))

    return StudyFactor(name=name,
                       factor_type=factor_type,
                       comments=comments)


StudyPublications_api_model = {
    # pubmed_id                     (str):
    # doi                           (str):
    # author_list -> authorList     (str):
    # title                         (str):
    # status                        (str, OntologyAnnotation):
    # comments                      (list, Comment):
    'pubMedID': fields.String(attribute='pubmed_id'),
    'doi': fields.String,
    'authorList': fields.String(attribute='author_list'),
    'title': fields.String,
    'status': fields.Nested(OntologyAnnotation_api_model),
    'comments': fields.List(fields.Nested(Comment_api_model))
}


def serialize_study_publication(isa_obj):
    assert isinstance(isa_obj, Publication)
    return {
        'pubMedID': isa_obj.pubmed_id,
        'doi': isa_obj.doi,
        'authorList': isa_obj.author_list,
        'title': isa_obj.title,
        'status': json.loads(json.dumps(isa_obj.status, default=serialize_ontology_annotation, sort_keys=True)),
        'comments': json.loads(json.dumps(isa_obj.comments, default=serialize_comment, sort_keys=True))
    }


def unserialize_study_publication(json_obj):
    pubmed_id = ''
    if 'pubMedID' in json_obj and json_obj['pubMedID'] is not None:
        pubmed_id = json_obj['pubMedID']
    doi = ''
    if 'doi' in json_obj and json_obj['doi'] is not None:
        doi = json_obj['doi']
    author_list = ''
    if 'authorList' in json_obj and json_obj['authorList'] is not None:
        author_list = json_obj['authorList']
    title = ''
    if 'title' in json_obj and json_obj['title'] is not None:
        title = json_obj['title']
    status = OntologyAnnotation()
    if 'status' in json_obj and json_obj['status'] is not None:
        status = unserialize_ontology_annotation(json_obj['status'])
    comments = list()
    if 'comments' in json_obj and json_obj['comments'] is not None:
        for comment in json_obj['comments']:
            comments.append(unserialize_comment(comment))

    return Publication(pubmed_id=pubmed_id,
                       doi=doi,
                       author_list=author_list,
                       title=title,
                       status=status,
                       comments=comments)


Characteristic_api_model = {
    # category (OntologyAnnotation):
    # value (OntologyAnnotation):
    # unit (OntologyAnnotation):
    # comments (list, Comment):
    'category': fields.Nested(OntologyAnnotation_api_model),
    'value': fields.Nested(OntologyAnnotation_api_model),
    'unit': fields.Nested(OntologyAnnotation_api_model),
    'comments': fields.List(fields.Nested(Comment_api_model))
}


def serialize_characteristic(isa_obj):
    assert isinstance(isa_obj, Characteristic)
    return {
        'category': json.loads(json.dumps(isa_obj.category, default=serialize_ontology_annotation, sort_keys=True)),
        'value': json.loads(json.dumps(isa_obj.value, default=serialize_ontology_annotation, sort_keys=True)),
        'unit': json.loads(json.dumps(isa_obj.unit, default=serialize_ontology_annotation, sort_keys=True)),
        'comments': json.loads(json.dumps(isa_obj.comments, default=serialize_comment, sort_keys=True))
    }


def unserialize_characteristic(json_obj):
    category = OntologyAnnotation()
    if 'category' in json_obj and json_obj['category'] is not None:
        category = unserialize_ontology_annotation(json_obj['category'])
    value = OntologyAnnotation()
    if 'value' in json_obj and json_obj['value'] is not None:
        value = unserialize_ontology_annotation(json_obj['value'])
    unit = OntologyAnnotation()
    if 'unit' in json_obj and json_obj['unit'] is not None:
        unit = unserialize_ontology_annotation(json_obj['value'])
    comments = list()
    if 'comments' in json_obj and json_obj['comments'] is not None:
        for comment in json_obj['comments']:
            comments.append(unserialize_comment(comment))

    return Characteristic(category=category,
                          value=value,
                          unit=unit,
                          comments=comments)


class FactorValueItem(fields.Raw):
    def format(self, value):
        val = None
        if isinstance(value, (int, float, str)):
            val = value
        if isinstance(value, OntologyAnnotation):
            val = {
                'annotationValue': value.term,
                'termSource': value.term_source,
                'termAccession':  value.term_accession,
                'comments':  value.comments
            }
        return val


FactorValue_api_model = {
    # factor_name -> factorName     (StudyFactor):
    # value                         (OntologyAnnotation):
    # unit                          (OntologyAnnotation):
    # comments                      (list, Comment):
    'factorName': fields.Nested(StudyFactor_api_model, attribute='factor_name'),
    'value': FactorValueItem(attribute='value'),
    'unit': fields.Nested(OntologyAnnotation_api_model),
    'comments': fields.List(fields.Nested(Comment_api_model))
}


def serialize_factor_value(isa_obj):
    assert isinstance(isa_obj, FactorValue)
    return {
        'factorName': json.loads(json.dumps(isa_obj.factor_name, default=serialize_study_factor, sort_keys=True)),
        'value': json.loads(json.dumps(isa_obj.value, default=serialize_ontology_annotation, sort_keys=True)),
        'unit': json.loads(json.dumps(isa_obj.unit, default=serialize_ontology_annotation, sort_keys=True)),
        'comments': json.loads(json.dumps(isa_obj.comments, default=serialize_comment, sort_keys=True))
    }


def unserialize_factor_value(json_obj):
    factor_name = StudyFactor()
    if 'factor_name' in json_obj and json_obj['factor_name'] is not None:
        factor_name = unserialize_study_factor(json_obj['factor_name'])
    value = OntologyAnnotation()
    if 'value' in json_obj and json_obj['value'] is not None:
        value = unserialize_ontology_annotation(json_obj['value'])
    unit = OntologyAnnotation()
    if 'unit' in json_obj and json_obj['unit'] is not None:
        unit = unserialize_ontology_annotation(json_obj['value'])
    comments = list()
    if 'comments' in json_obj and json_obj['comments'] is not None:
        for comment in json_obj['comments']:
            comments.append(unserialize_comment(comment))

    return FactorValue(factor_name=factor_name,
                       value=value,
                       unit=unit,
                       comments=comments)


StudySource_api_model = {
    # name (str):
    # characteristics (list, OntologyAnnotation):
    # comments (list, Comment):
    'name': fields.String,
    'characteristics': fields.List(fields.Nested(Characteristic_api_model)),
    'comments': fields.List(fields.Nested(Comment_api_model))
}


def serialize_study_source(isa_obj):
    assert isinstance(isa_obj, Source)
    return {
        'name': isa_obj.name,
        'characteristics': json.loads(
            json.dumps(isa_obj.characteristics, default=serialize_characteristic, sort_keys=True)),
        'comments': json.loads(json.dumps(isa_obj.comments, default=serialize_comment, sort_keys=True))
    }


def unserialize_study_source(json_obj):
    name = ''
    if 'name' in json_obj and json_obj['name'] is not None:
        name = json_obj['name']
    characteristics = list()
    if 'characteristics' in json_obj and json_obj['characteristics'] is not None:
        for characteristic in json_obj['characteristics']:
            characteristics.append(unserialize_characteristic(characteristic))
    comments = list()
    if 'comments' in json_obj and json_obj['comments'] is not None:
        for comment in json_obj['comments']:
            comments.append(unserialize_comment(comment))

    return Source(name=name,
                  characteristics=characteristics,
                  comments=comments)


StudySample_api_model = {
    # name                              (str):
    # characteristics                   (list, OntologyAnnotation):
    # factor_values -> factorValues     (FactorValues):
    # derives_from                      (Source):
    # comments                          (list, Comment):
    'name': fields.String,
    'characteristics': fields.List(fields.Nested(Characteristic_api_model)),
    'derives_from': fields.List(fields.Nested(StudySource_api_model)),
    'factorValues': fields.List(fields.Nested(FactorValue_api_model), attribute='factor_values'),
    'comments': fields.List(fields.Nested(Comment_api_model))
}


def serialize_study_sample(isa_obj):
    assert isinstance(isa_obj, Sample)
    return {
        'name': isa_obj.name,
        'characteristics': json.loads(
            json.dumps(isa_obj.characteristics, default=serialize_characteristic, sort_keys=True)),
        'factor_values': json.loads(
            json.dumps(isa_obj.factor_values, default=serialize_factor_value, sort_keys=True)),
        'derives_from': json.loads(
            json.dumps(isa_obj.derives_from, default=serialize_study_source, sort_keys=True)),
        'comments': json.loads(json.dumps(isa_obj.comments, default=serialize_comment, sort_keys=True))
    }


def unserialize_study_sample(json_obj):
    name = ''
    if 'name' in json_obj and json_obj['name'] is not None:
        name = json_obj['name']
    characteristics = list()
    if 'characteristics' in json_obj and json_obj['characteristics'] is not None:
        for characteristic in json_obj['characteristics']:
            characteristics.append(unserialize_characteristic(characteristic))
    derives_from = ''
    if 'derives_from' in json_obj and json_obj['derives_from'] is not None:
        derives_from = json_obj['derives_from']
    factor_values = list()
    if 'factor_values' in json_obj and json_obj['factor_values'] is not None:
        for factor_value in json_obj['factor_values']:
            factor_values.append(unserialize_factor_value(factor_value))
    comments = list()
    if 'comments' in json_obj and json_obj['comments'] is not None:
        for comment in json_obj['comments']:
            comments.append(unserialize_comment(comment))

    return Sample(name=name, characteristics=characteristics,
                  derives_from=derives_from, factor_values=factor_values,
                  comments=comments)


StudyMaterial_api_model = {
    # other_materials -> otherMaterials     (list, OntologyAnnotation):
    # sources                               (StudySource):
    # samples                               (StudySample):
    # comments                              (list, Comment):
    'otherMaterials': fields.List(fields.Nested(Characteristic_api_model, attribute='other_materials')),
    'sources': fields.List(fields.Nested(StudySource_api_model)),
    'samples': fields.List(fields.Nested(StudySample_api_model)),
    'comments': fields.List(fields.Nested(Comment_api_model))
}
